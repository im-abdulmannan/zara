"""Habit service: CRUD + automatic scheduler reminders.

Like the reminder service, this shares the AutomationEngine. Each active habit
gets a recurring job whose id is prefixed ``habit:`` so it never collides with
reminder jobs. When a habit job fires, this service enqueues a notification
(spoken + toast) telling the user to do the habit. Streaks are advanced via
:meth:`mark_done`, not by the reminder firing.
"""
from __future__ import annotations

import uuid
from typing import Any, List, Mapping, Optional, Tuple

from automation import (
    AutomationEngine,
    JobSpec,
    ReminderType,
    register_handler,
    unregister_handler,
)
from automation.exceptions import DuplicateJobError, JobNotFoundError
from automation.logging_config import get_logger
from habits.config import HabitConfig
from habits.models import Habit, HabitFrequency, HabitStatus
from habits.repository import HabitRepository
from notifications import Notification

# Job-id namespace so habit jobs don't collide with reminder jobs in the engine.
_JOB_PREFIX = "habit:"


def _job_id(habit_id: str) -> str:
    return f"{_JOB_PREFIX}{habit_id}"


def _is_habit_job(job_id: str) -> bool:
    return job_id.startswith(_JOB_PREFIX)


def _habit_id_from_job(job_id: str) -> str:
    return job_id[len(_JOB_PREFIX):]


class HabitService:
    """High-level API for habits with automatic scheduled reminders."""

    def __init__(
        self,
        engine: AutomationEngine,
        repository: Optional[HabitRepository] = None,
        notification_queue: Optional[object] = None,
        config: Optional[HabitConfig] = None,
    ) -> None:
        """Args:
        engine: shared automation engine.
        repository: habit persistence.
        notification_queue: object with ``.put(notification)`` (e.g. the
            notification worker sink). If None, reminders are scheduled but not
            delivered anywhere.
        """
        self._config = config or HabitConfig.from_env()
        self._logger = get_logger(__name__, self._config.log_level)
        self._engine = engine
        self._repo = repository or HabitRepository(self._config)
        self._queue = notification_queue
        register_handler(self._on_habit_fired)

    # -- lifecycle ---------------------------------------------------------
    def start(self) -> None:
        """Ensures the engine is running and (re)schedules all active habits."""
        self._engine.start()
        active = self._repo.list_all(status=HabitStatus.ACTIVE)
        for habit in active:
            self._schedule(habit)
        self._logger.info("Habit service started; scheduled %d habit(s).", len(active))

    def shutdown(self) -> None:
        """Detaches the fired handler (engine shutdown is owned by the runtime)."""
        unregister_handler(self._on_habit_fired)

    # -- CRUD --------------------------------------------------------------
    def create_habit(
        self,
        title: str,
        frequency: "str | HabitFrequency" = HabitFrequency.DAILY,
        time: str = "09:00",
    ) -> Habit:
        """Creates, persists, and schedules a habit reminder."""
        habit = Habit(
            id=uuid.uuid4().hex,
            title=title,
            frequency=HabitFrequency.from_value(frequency),
            time=time,
            status=HabitStatus.ACTIVE,
            streak=0,
        )
        self._repo.add(habit)
        self._schedule(habit)
        self._logger.info(
            "Created habit id=%s %r %s at %s.",
            habit.id,
            habit.title,
            habit.frequency.value,
            habit.time.strftime("%H:%M"),
        )
        return habit

    def update_habit(
        self,
        habit_id: str,
        *,
        title: Optional[str] = None,
        frequency: "Optional[str | HabitFrequency]" = None,
        time: Optional[str] = None,
    ) -> Habit:
        """Updates a habit and reschedules its reminder."""
        habit = self._repo.get_or_raise(habit_id)
        if title is not None:
            habit.title = title
        if frequency is not None:
            habit.frequency = HabitFrequency.from_value(frequency)
        if time is not None:
            habit.time = time
        habit.__post_init__()
        self._repo.update(habit)
        self._safe_delete_job(habit.id)
        if habit.status == HabitStatus.ACTIVE:
            self._schedule(habit)
        self._logger.info("Updated habit id=%s.", habit_id)
        return habit

    def delete_habit(self, habit_id: str) -> None:
        """Deletes a habit and removes its scheduled reminder."""
        self._safe_delete_job(habit_id)
        self._repo.delete(habit_id)
        self._logger.info("Deleted habit id=%s.", habit_id)

    def mark_done(self, habit_id: str) -> Habit:
        """Marks today's habit as completed and advances the streak."""
        habit = self._repo.get_or_raise(habit_id)
        habit.streak += 1
        self._repo.update(habit)
        self._logger.info("Habit id=%s marked done; streak=%d.", habit_id, habit.streak)
        return habit

    def pause_habit(self, habit_id: str) -> Habit:
        habit = self._repo.get_or_raise(habit_id)
        self._safe_delete_job(habit_id)
        habit.status = HabitStatus.PAUSED
        self._repo.update(habit)
        self._logger.info("Paused habit id=%s.", habit_id)
        return habit

    def resume_habit(self, habit_id: str) -> Habit:
        habit = self._repo.get_or_raise(habit_id)
        habit.status = HabitStatus.ACTIVE
        self._repo.update(habit)
        self._schedule(habit)
        self._logger.info("Resumed habit id=%s.", habit_id)
        return habit

    def list_habits(self, status: Optional[HabitStatus] = None) -> List[Habit]:
        """Lists habits, optionally filtered by status."""
        return self._repo.list_all(status=status)

    def get_habit(self, habit_id: str) -> Habit:
        return self._repo.get_or_raise(habit_id)

    # -- scheduling internals ---------------------------------------------
    def _schedule(self, habit: Habit) -> None:
        reminder_type, schedule = self._to_trigger_schedule(habit)
        spec = JobSpec(
            name=f"Habit: {habit.title}",
            message=f"Time to {habit.title}.",
            reminder_type=reminder_type,
            schedule=schedule,
            job_id=_job_id(habit.id),
            metadata={"habit_id": habit.id, "frequency": habit.frequency.value},
        )
        try:
            self._engine.create_job(spec)
        except DuplicateJobError:
            self._logger.debug("Habit job already scheduled: %s.", habit.id)

    def _to_trigger_schedule(
        self, habit: Habit
    ) -> Tuple[ReminderType, Mapping[str, Any]]:
        hour, minute = habit.time.hour, habit.time.minute
        freq = habit.frequency
        if freq is HabitFrequency.DAILY:
            return ReminderType.DAILY, {"hour": hour, "minute": minute}
        if freq is HabitFrequency.WEEKDAY:
            return ReminderType.WEEKLY, {
                "day_of_week": "mon-fri", "hour": hour, "minute": minute,
            }
        if freq is HabitFrequency.WEEKEND:
            return ReminderType.WEEKLY, {
                "day_of_week": "sat,sun", "hour": hour, "minute": minute,
            }
        if freq is HabitFrequency.WEEKLY:
            return ReminderType.WEEKLY, {
                "day_of_week": "mon", "hour": hour, "minute": minute,
            }
        # MONTHLY
        return ReminderType.MONTHLY, {"day": 1, "hour": hour, "minute": minute}

    def _safe_delete_job(self, habit_id: str) -> None:
        try:
            self._engine.delete_job(_job_id(habit_id))
        except JobNotFoundError:
            self._logger.debug("No habit job to delete for %s.", habit_id)

    # -- fired handler (runs on a scheduler worker thread) -----------------
    def _on_habit_fired(
        self,
        reminder_id: str,
        name: str,
        message: str,
        metadata: Mapping[str, Any],
    ) -> None:
        """Engine callback. Only handles habit jobs (ignores others)."""
        if not _is_habit_job(reminder_id):
            return
        habit_id = _habit_id_from_job(reminder_id)
        habit = self._repo.get(habit_id)
        if habit is None:
            self._logger.warning("Fired habit %s no longer exists.", habit_id)
            return
        if self._queue is not None:
            self._queue.put(
                Notification(
                    title="Habit reminder",
                    message=f"Time to {habit.title}.",
                    source="habit",
                )
            )
        self._logger.info("Habit reminder fired: %r.", habit.title)
