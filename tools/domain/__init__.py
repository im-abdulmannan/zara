"""Domain tools backed by ZaraRuntime (reminders, habits, notes, etc.)."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping

from calendar_query import CalendarQueryParseError
from habits.exceptions import HabitValidationError
from runtime import get_runtime
from time_parser import parse_when
from time_parser.exceptions import TimeParseError
from tools.base import BaseTool, ToolParameter, ToolResult


def _format_time(when: datetime) -> str:
    return when.strftime("%I:%M %p").lstrip("0")


def _format_clock(clock_time) -> str:
    return clock_time.strftime("%I:%M %p").lstrip("0")


def _find_habit(habits, params: Mapping[str, Any]):
    target = None
    index = params.get("index")
    query = (params.get("title") or params.get("query") or "").lower().strip()

    if index is not None:
        try:
            position = int(index) - 1
            if 0 <= position < len(habits):
                target = habits[position]
        except (TypeError, ValueError):
            target = None

    if target is None and query:
        target = next((h for h in habits if query in h.title.lower()), None)
    return target


def _format_habit_choices(habits) -> str:
    return "; ".join(
        f"{idx}. {habit.title} at {_format_clock(habit.time)}"
        for idx, habit in enumerate(habits, start=1)
    )


class RememberTool(BaseTool):
    name = "remember"
    description = "Save a durable fact, preference, name, or task."
    parameters = (
        ToolParameter("kind", "One of: name, preference, fact, task"),
        ToolParameter("value", "The information to remember"),
        ToolParameter("key", "Preference key when kind is preference", required=False),
        ToolParameter("response", "Spoken confirmation override", required=False),
    )

    def execute(self, params: Mapping[str, Any]) -> ToolResult:
        kind = (params.get("kind") or "fact").lower().strip()
        value = params.get("value")
        if not value:
            return ToolResult(False, "What would you like me to remember?")
        if kind == "preference" and not params.get("key"):
            return ToolResult(False, "What is that a preference for?")
        get_runtime().remember(kind, value, key=(params.get("key") or ""))
        return ToolResult(True, params.get("response") or "I'll remember that.")


class SetReminderTool(BaseTool):
    name = "set_reminder"
    description = "Schedule a one-time or recurring reminder."
    parameters = (
        ToolParameter("title", "What to remind about"),
        ToolParameter("time", "Time as HH:MM or natural language", required=False),
        ToolParameter("datetime", "ISO datetime override", required=False),
        ToolParameter("repeat", "once|daily|weekly|monthly", required=False),
        ToolParameter("description", "Optional details", required=False),
        ToolParameter("response", "Spoken confirmation override", required=False),
    )

    def execute(self, params: Mapping[str, Any]) -> ToolResult:
        title = params.get("title") or params.get("value")
        time_str = params.get("time") or params.get("datetime")
        if not title:
            return ToolResult(False, "What should I remind you about?")
        if not time_str:
            return ToolResult(False, "What time should I set the reminder for?")
        try:
            when_iso = params.get("datetime")
            when = (
                datetime.fromisoformat(str(when_iso))
                if when_iso
                else parse_when(str(time_str))
            )
        except (ValueError, TypeError, TimeParseError):
            return ToolResult(
                False,
                f"I couldn't understand the time '{time_str}'. Try something like 10:25 PM.",
            )
        reminder = get_runtime().schedule_reminder(
            title=title,
            when=when,
            description=params.get("description", "") or "",
            repeat=params.get("repeat", "once") or "once",
        )
        spoken = params.get("response") or (
            f"Okay, I'll remind you to {reminder.title} at {_format_time(when)}."
        )
        return ToolResult(True, spoken)


class ListRemindersTool(BaseTool):
    name = "list_reminders"
    description = "List active reminders."
    parameters: tuple = ()

    def execute(self, params: Mapping[str, Any]) -> ToolResult:
        reminders = get_runtime().active_reminders()
        if not reminders:
            return ToolResult(True, "You have no active reminders.")
        parts = [
            f"{idx}. {r.title} at {_format_time(r.remind_at)}"
            for idx, r in enumerate(reminders, start=1)
        ]
        return ToolResult(True, "Your reminders are: " + "; ".join(parts) + ".")


class CancelReminderTool(BaseTool):
    name = "cancel_reminder"
    description = "Cancel an active reminder by index or title."
    parameters = (
        ToolParameter("index", "1-based index from list_reminders", required=False),
        ToolParameter("title", "Words from reminder title", required=False),
        ToolParameter("response", "Spoken confirmation override", required=False),
    )

    def execute(self, params: Mapping[str, Any]) -> ToolResult:
        reminders = get_runtime().active_reminders()
        if not reminders:
            return ToolResult(True, "You have no reminders to cancel.")

        target = None
        index = params.get("index")
        query = (params.get("title") or params.get("query") or "").lower().strip()
        if index is not None:
            try:
                position = int(index) - 1
                if 0 <= position < len(reminders):
                    target = reminders[position]
            except (TypeError, ValueError):
                target = None
        if target is None and query:
            target = next((r for r in reminders if query in r.title.lower()), None)

        if target is None:
            parts = [
                f"{idx}. {r.title} at {_format_time(r.remind_at)}"
                for idx, r in enumerate(reminders, start=1)
            ]
            return ToolResult(
                False,
                "Which reminder should I cancel? You have: " + "; ".join(parts) + ".",
            )

        get_runtime().cancel_reminder(target.id)
        return ToolResult(
            True,
            params.get("response") or f"I've cancelled the reminder for {target.title}.",
        )


class CreateHabitTool(BaseTool):
    name = "create_habit"
    description = "Create a recurring habit with optional schedule."
    parameters = (
        ToolParameter("title", "Habit title"),
        ToolParameter("frequency", "daily|weekday|weekend|weekly|monthly", required=False),
        ToolParameter("time", "24-hour HH:MM", required=False),
        ToolParameter("response", "Spoken confirmation override", required=False),
    )

    def execute(self, params: Mapping[str, Any]) -> ToolResult:
        title = params.get("title") or params.get("value")
        frequency = params.get("frequency") or "daily"
        time_str = params.get("time") or "09:00"
        if not title:
            return ToolResult(False, "What habit would you like to track?")
        try:
            habit = get_runtime().create_habit(
                title=title, frequency=frequency, at_time=time_str
            )
        except HabitValidationError as exc:
            return ToolResult(False, str(exc))
        except ValueError:
            return ToolResult(
                False,
                f"I couldn't understand the time '{time_str}'. Try 09:00 or 7 PM.",
            )
        spoken = params.get("response") or (
            f"Added {habit.title}. I'll remind you "
            f"{habit.frequency.value} at {_format_clock(habit.time)}."
        )
        return ToolResult(True, spoken)


class ListHabitsTool(BaseTool):
    name = "list_habits"
    description = "List tracked habits."
    parameters = (
        ToolParameter("include_paused", "Include paused habits", required=False, type="boolean"),
    )

    def execute(self, params: Mapping[str, Any]) -> ToolResult:
        include_paused = bool(params.get("include_paused"))
        habits = (
            get_runtime().all_habits()
            if include_paused
            else get_runtime().active_habits()
        )
        if not habits:
            return ToolResult(True, "You have no habits yet.")
        parts = [
            (
                f"{idx}. {h.title}, {h.frequency.value} at "
                f"{_format_clock(h.time)}, streak {h.streak}, {h.status.value}"
            )
            for idx, h in enumerate(habits, start=1)
        ]
        return ToolResult(True, "Your habits are: " + "; ".join(parts) + ".")


class MarkHabitDoneTool(BaseTool):
    name = "mark_habit_done"
    description = "Mark a habit as completed for today."
    parameters = (
        ToolParameter("index", "1-based index", required=False),
        ToolParameter("title", "Words from habit title", required=False),
        ToolParameter("response", "Spoken confirmation override", required=False),
    )

    def execute(self, params: Mapping[str, Any]) -> ToolResult:
        habits = get_runtime().active_habits()
        if not habits:
            return ToolResult(True, "You have no active habits to mark done.")
        target = _find_habit(habits, params)
        if target is None:
            return ToolResult(
                False,
                "Which habit should I mark done? You have: "
                + _format_habit_choices(habits)
                + ".",
            )
        habit = get_runtime().mark_habit_done(target.id)
        return ToolResult(
            True,
            params.get("response") or f"Nice. {habit.title} is done. Your streak is {habit.streak}.",
        )


class PauseHabitTool(BaseTool):
    name = "pause_habit"
    description = "Pause an active habit."
    parameters = (
        ToolParameter("index", "1-based index", required=False),
        ToolParameter("title", "Words from habit title", required=False),
        ToolParameter("response", "Spoken confirmation override", required=False),
    )

    def execute(self, params: Mapping[str, Any]) -> ToolResult:
        habits = get_runtime().active_habits()
        if not habits:
            return ToolResult(True, "You have no active habits to pause.")
        target = _find_habit(habits, params)
        if target is None:
            return ToolResult(
                False,
                "Which habit should I pause? You have: "
                + _format_habit_choices(habits)
                + ".",
            )
        habit = get_runtime().pause_habit(target.id)
        return ToolResult(True, params.get("response") or f"Paused {habit.title}.")


class ResumeHabitTool(BaseTool):
    name = "resume_habit"
    description = "Resume a paused habit."
    parameters = (
        ToolParameter("index", "1-based index", required=False),
        ToolParameter("title", "Words from habit title", required=False),
        ToolParameter("response", "Spoken confirmation override", required=False),
    )

    def execute(self, params: Mapping[str, Any]) -> ToolResult:
        habits = [h for h in get_runtime().all_habits() if h.status.value == "paused"]
        if not habits:
            return ToolResult(True, "You have no paused habits to resume.")
        target = _find_habit(habits, params)
        if target is None:
            return ToolResult(
                False,
                "Which habit should I resume? You have: "
                + _format_habit_choices(habits)
                + ".",
            )
        habit = get_runtime().resume_habit(target.id)
        return ToolResult(True, params.get("response") or f"Resumed {habit.title}.")


class DeleteHabitTool(BaseTool):
    name = "delete_habit"
    description = "Delete a habit permanently."
    parameters = (
        ToolParameter("index", "1-based index", required=False),
        ToolParameter("title", "Words from habit title", required=False),
        ToolParameter("response", "Spoken confirmation override", required=False),
    )

    def execute(self, params: Mapping[str, Any]) -> ToolResult:
        habits = get_runtime().all_habits()
        if not habits:
            return ToolResult(True, "You have no habits to delete.")
        target = _find_habit(habits, params)
        if target is None:
            return ToolResult(
                False,
                "Which habit should I delete? You have: "
                + _format_habit_choices(habits)
                + ".",
            )
        get_runtime().delete_habit(target.id)
        return ToolResult(True, params.get("response") or f"Deleted {target.title}.")


class QueryCalendarTool(BaseTool):
    name = "query_calendar"
    description = "Answer questions about meetings, reminders, and schedule."
    parameters = (
        ToolParameter("question", "Natural language calendar question"),
    )

    def execute(self, params: Mapping[str, Any]) -> ToolResult:
        question = params.get("question") or params.get("query")
        if not question:
            return ToolResult(False, "What would you like to know about your schedule?")
        try:
            result = get_runtime().query_calendar(question)
        except CalendarQueryParseError:
            return ToolResult(False, "I didn't understand that calendar question.")
        return ToolResult(True, result.answer)


class CreateMeetingTool(BaseTool):
    name = "create_meeting"
    description = "Schedule a meeting or appointment."
    parameters = (
        ToolParameter("title", "Meeting title"),
        ToolParameter("date", "today|tomorrow|YYYY-MM-DD", required=False),
        ToolParameter("time", "24-hour HH:MM", required=False),
        ToolParameter("location", "Optional location", required=False),
        ToolParameter("participants", "Optional attendees", required=False),
        ToolParameter("notes", "Optional notes", required=False),
        ToolParameter("response", "Spoken confirmation override", required=False),
    )

    def execute(self, params: Mapping[str, Any]) -> ToolResult:
        title = params.get("title") or params.get("value")
        if not title:
            return ToolResult(False, "What is the meeting about?")
        meeting = get_runtime().create_meeting(
            title=title,
            date=params.get("date") or "today",
            time=params.get("time") or "09:00",
            location=params.get("location", "") or "",
            participants=params.get("participants", "") or "",
            notes=params.get("notes", "") or "",
        )
        spoken = params.get("response") or (
            f"Scheduled {meeting.title} on {meeting.date.isoformat()} "
            f"at {_format_clock(meeting.time)}."
        )
        return ToolResult(True, spoken)


class CreateNoteTool(BaseTool):
    name = "create_note"
    description = "Create and save a note."
    parameters = (
        ToolParameter("title", "Note title"),
        ToolParameter("content", "Note body"),
        ToolParameter("tags", "Optional comma-separated tags", required=False),
        ToolParameter("response", "Spoken confirmation override", required=False),
    )

    def execute(self, params: Mapping[str, Any]) -> ToolResult:
        title = params.get("title") or params.get("value")
        content = params.get("content") or params.get("body")
        if not title:
            return ToolResult(False, "What should I call this note?")
        if not content:
            return ToolResult(False, "What should the note say?")
        note = get_runtime().create_note(
            title=title,
            content=content,
            tags=params.get("tags", "") or "",
        )
        return ToolResult(True, params.get("response") or f"Saved note {note.title}.")


class SearchNotesTool(BaseTool):
    name = "search_notes"
    description = "Search saved notes by text."
    parameters = (
        ToolParameter("query", "Search text"),
    )

    def execute(self, params: Mapping[str, Any]) -> ToolResult:
        query = params.get("query") or params.get("question")
        if not query:
            return ToolResult(False, "What note should I search for?")
        notes = get_runtime().search_notes(query)
        if not notes:
            return ToolResult(True, f"I couldn't find any notes matching {query}.")
        parts = [
            f"{idx}. {note.title}: {note.content[:80]}"
            for idx, note in enumerate(notes[:5], start=1)
        ]
        return ToolResult(True, "Here is what I found: " + "; ".join(parts) + ".")


class ListNotesTool(BaseTool):
    name = "list_notes"
    description = "List all saved notes."
    parameters: tuple = ()

    def execute(self, params: Mapping[str, Any]) -> ToolResult:
        notes = get_runtime().list_notes()
        if not notes:
            return ToolResult(True, "You have no notes yet.")
        parts = [f"{idx}. {note.title}" for idx, note in enumerate(notes[:10], start=1)]
        return ToolResult(True, "Your notes are: " + "; ".join(parts) + ".")


class QueryMemoryTool(BaseTool):
    name = "query_memory"
    description = "Recall stored facts about the user."
    parameters = (
        ToolParameter("query", "Optional search text", required=False),
    )

    def execute(self, params: Mapping[str, Any]) -> ToolResult:
        query = params.get("query") or params.get("question")
        if query:
            memories = get_runtime().query_memory(query)
            if not memories:
                return ToolResult(True, f"I don't remember anything about {query}.")
            parts = [f"{memory.key}: {memory.value}" for memory in memories[:8]]
            return ToolResult(True, "I remember: " + "; ".join(parts) + ".")
        summary = get_runtime().memory_summary_text()
        if not summary.strip() or summary.startswith("No stored"):
            return ToolResult(True, "I don't have anything stored about you yet.")
        return ToolResult(True, summary)
