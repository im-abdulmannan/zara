"""Composition root for the Zara assistant.

Single DI entry point — all subsystems are constructed here and exposed via
a small facade. The voice loop, agent, and tool registry must use
``get_runtime()`` instead of constructing domain services directly.

Architecture::

    Voice (app.py)
        -> STT (voice/stt)
        -> Agent (agent.py)
            -> Intent Classifier (intent/)
            -> Intent Router (router/)
            -> LLM fallback (OpenRouter)
        -> Tool Registry (tools/registry.py)
        -> ZaraRuntime (this module)
            -> ReminderService + ReminderScheduler -> AutomationEngine (APScheduler)
            -> HabitService -> AutomationEngine (shared, non-blocking)
            -> MeetingService, NoteService, MemoryService (SQLite)
            -> CalendarQueryEngine (meetings + reminders)
            -> NotificationWorker + TTSSpeaker (background queue)
"""
from __future__ import annotations

import re
from datetime import datetime, time
from typing import List, Optional

from automation import AutomationEngine
from automation.logging_config import get_logger
from calendar_query import CalendarQueryEngine
from habits import Habit, HabitFrequency, HabitRepository, HabitService, HabitStatus
from meetings import Meeting, MeetingRepository, MeetingService
from memories import Memory, MemoryRepository, MemoryService
from notes import Note, NoteRepository, NoteService
from notifications import NotificationWorker, TTSSpeaker, create_desktop_notifier
from reminders import (
    Reminder,
    ReminderRepository,
    ReminderScheduler,
    ReminderService,
    ReminderStatus,
    RepeatType,
)
from time_parser.clock import parse_next_clock_datetime

_logger = get_logger(__name__)


def parse_reminder_time(text: str, now: Optional[datetime] = None) -> datetime:
    """Parse a clock time string into the next future :class:`datetime`."""
    return parse_next_clock_datetime(text, now=now)


def parse_habit_time(text: str) -> time:
    """Parse a spoken/typed time into a clock time for recurring habits."""
    when = parse_reminder_time(text)
    return when.time().replace(second=0, microsecond=0)


def _memory_key(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "_", str(value).lower()).strip("_")
    return cleaned[:80] or "fact"


class _WorkerSink:
    """Adapts the :class:`NotificationWorker` to the ``.put()`` interface."""

    def __init__(self, worker: NotificationWorker) -> None:
        self._worker = worker

    def put(self, message: object) -> None:
        self._worker.enqueue(message)


class ZaraRuntime:
    """Owns and coordinates the assistant's background services."""

    def __init__(self) -> None:
        self.speaker = TTSSpeaker()
        self.desktop_notifier = create_desktop_notifier(app_name="Zara")
        self.worker = NotificationWorker(
            speaker=self.speaker,
            desktop_notifier=self.desktop_notifier,
        )
        self.engine = AutomationEngine()
        self.repository = ReminderRepository()
        self.reminder_scheduler = ReminderScheduler(engine=self.engine)
        self.reminder_service = ReminderService(
            scheduler=self.reminder_scheduler,
            repository=self.repository,
            notification_queue=_WorkerSink(self.worker),
        )
        self.meeting_repository = MeetingRepository()
        self.meeting_service = MeetingService(repository=self.meeting_repository)
        self.note_repository = NoteRepository()
        self.note_service = NoteService(repository=self.note_repository)
        self.memory_repository = MemoryRepository()
        self.memory_service = MemoryService(repository=self.memory_repository)
        self.calendar_engine = CalendarQueryEngine(
            meeting_service=self.meeting_service,
            reminder_service=self.reminder_service,
        )
        self.habit_repository = HabitRepository()
        self.habit_service = HabitService(
            engine=self.engine,
            repository=self.habit_repository,
            notification_queue=_WorkerSink(self.worker),
        )
        self._started = False

    def start(self) -> None:
        if self._started:
            return
        self.worker.start()
        self.reminder_service.start()
        self.habit_service.start()
        self._started = True
        _logger.info("Zara runtime started.")

    def shutdown(self) -> None:
        if not self._started:
            return
        self.habit_service.shutdown()
        self.reminder_service.shutdown()
        self.worker.stop()
        self._started = False
        _logger.info("Zara runtime shut down.")

    def speak(self, text: str) -> None:
        self.speaker.speak(text)

    # -- reminders --------------------------------------------------------
    def schedule_reminder(
        self,
        title: str,
        when: datetime,
        description: str = "",
        repeat: "str | RepeatType" = RepeatType.ONCE,
    ) -> Reminder:
        return self.reminder_service.create_reminder(
            title=title, remind_at=when, description=description, repeat_type=repeat
        )

    def active_reminders(self) -> List[Reminder]:
        return self.reminder_service.list_reminders(status=ReminderStatus.SCHEDULED)

    def cancel_reminder(self, reminder_id: str) -> Reminder:
        return self.reminder_service.cancel_reminder(reminder_id)

    # -- habits -----------------------------------------------------------
    def create_habit(
        self,
        title: str,
        frequency: "str | HabitFrequency" = HabitFrequency.DAILY,
        at_time: str = "09:00",
    ) -> Habit:
        parsed_time = parse_habit_time(at_time)
        return self.habit_service.create_habit(
            title=title,
            frequency=frequency,
            time=parsed_time.strftime("%H:%M"),
        )

    def active_habits(self) -> List[Habit]:
        return self.habit_service.list_habits(status=HabitStatus.ACTIVE)

    def all_habits(self) -> List[Habit]:
        return self.habit_service.list_habits()

    def mark_habit_done(self, habit_id: str) -> Habit:
        return self.habit_service.mark_done(habit_id)

    def pause_habit(self, habit_id: str) -> Habit:
        return self.habit_service.pause_habit(habit_id)

    def resume_habit(self, habit_id: str) -> Habit:
        return self.habit_service.resume_habit(habit_id)

    def delete_habit(self, habit_id: str) -> None:
        self.habit_service.delete_habit(habit_id)

    # -- calendar ---------------------------------------------------------
    def query_calendar(self, question: str):
        return self.calendar_engine.query(question)

    # -- meetings ---------------------------------------------------------
    def create_meeting(
        self,
        title: str,
        date: str,
        time: str,
        *,
        location: str = "",
        participants: str = "",
        notes: str = "",
    ) -> Meeting:
        return self.meeting_service.create_meeting(
            title=title,
            date=date,
            time=time,
            location=location,
            participants=participants,
            notes=notes,
        )

    # -- notes ------------------------------------------------------------
    def create_note(self, title: str, content: str, *, tags: str = "") -> Note:
        return self.note_service.create_note(
            title=title, content=content, tags=tags or None
        )

    def search_notes(self, query: str) -> List[Note]:
        return self.note_service.search_note(query)

    def list_notes(self) -> List[Note]:
        return self.note_service.list_notes()

    # -- long-term memory -------------------------------------------------
    def remember(self, kind: str, value: str, *, key: str = "") -> Memory:
        """Persist a durable memory via the injected :class:`MemoryService`."""
        kind = (kind or "fact").lower().strip()
        if kind == "name":
            return self.memory_service.remember("name", value, category="user")
        if kind == "preference":
            pref_key = key or _memory_key(value)
            return self.memory_service.remember(pref_key, value, category="preference")
        if kind == "task":
            from memory.store import add_task

            add_task(value)
            return self.memory_service.remember(
                _memory_key(value), value, category="task"
            )
        return self.memory_service.remember(_memory_key(value), value, category="fact")

    def query_memory(self, query: str | None = None) -> List[Memory]:
        if query and query.strip():
            return self.memory_service.search_memory(query.strip())
        return self.memory_service.list_memories()

    def memory_summary_text(self) -> str:
        """Prompt-ready summary combining SQLite facts and short-term tasks."""
        from memory.store import memory_summary

        return memory_summary()


_runtime: Optional[ZaraRuntime] = None


def get_runtime() -> ZaraRuntime:
    global _runtime
    if _runtime is None:
        _runtime = ZaraRuntime()
        _runtime.start()
    return _runtime


def shutdown_runtime() -> None:
    global _runtime
    if _runtime is not None:
        _runtime.shutdown()
        _runtime = None
