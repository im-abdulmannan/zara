"""Format calendar query results for speech and display."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Iterable, List, Optional

from calendar_query.models import CalendarQueryResult, DaySchedule, QueryType
from meetings.models import Meeting
from reminders.models import Reminder


def _format_clock(value: datetime) -> str:
    return value.strftime("%I:%M %p").lstrip("0")


def _format_day(value: date) -> str:
    return value.strftime("%A, %B %d")


def _format_meeting(meeting: Meeting) -> str:
    parts = [meeting.title, _format_clock(meeting.starts_at)]
    if meeting.location:
        parts.append(f"at {meeting.location}")
    return " ".join(parts)


def _format_reminder(reminder: Reminder, *, day: Optional[date] = None) -> str:
    when = reminder.remind_at
    if day is not None:
        when = datetime.combine(day, reminder.remind_at.time())
    repeat = reminder.repeat_type.value
    if repeat == "once":
        return f"{reminder.title} at {_format_clock(when)}"
    return f"{reminder.title} at {_format_clock(when)} ({repeat})"


def _join_items(items: List[str]) -> str:
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return ", ".join(items[:-1]) + f", and {items[-1]}"


def format_day_schedule(schedule: DaySchedule) -> str:
    """Format a day schedule into spoken text."""
    label = "Today" if schedule.day == date.today() else _format_day(schedule.day)
    if schedule.is_empty:
        return f"You have nothing scheduled for {label.lower()}."

    parts: List[str] = []
    if schedule.meetings:
        meeting_text = _join_items([_format_meeting(m) for m in schedule.meetings])
        noun = "meeting" if len(schedule.meetings) == 1 else "meetings"
        parts.append(f"{len(schedule.meetings)} {noun}: {meeting_text}")

    if schedule.reminders:
        reminder_text = _join_items(
            [_format_reminder(r, day=schedule.day) for r in schedule.reminders]
        )
        noun = "reminder" if len(schedule.reminders) == 1 else "reminders"
        parts.append(f"{len(schedule.reminders)} {noun}: {reminder_text}")

    return f"For {label.lower()}, you have " + "; ".join(parts) + "."


def format_meetings_this_week(meetings: Iterable[Meeting]) -> str:
    items = list(meetings)
    if not items:
        return "You have no meetings this week."
    if len(items) == 1:
        return f"Yes. You have one meeting this week: {_format_meeting(items[0])}."
    parts = [_format_meeting(meeting) for meeting in items]
    return (
        f"Yes. You have {len(items)} meetings this week: "
        + _join_items(parts)
        + "."
    )


def format_next_meeting(meeting: Optional[Meeting]) -> str:
    if meeting is None:
        return "You have no upcoming meetings."
    day_label = "today" if meeting.date == date.today() else _format_day(meeting.date)
    location = f" at {meeting.location}" if meeting.location else ""
    return (
        f"Your next meeting is {meeting.title} on {day_label} "
        f"at {_format_clock(meeting.starts_at)}{location}."
    )


def format_all_reminders(reminders: Iterable[Reminder]) -> str:
    items = list(reminders)
    if not items:
        return "You have no reminders."
    parts = [_format_reminder(reminder) for reminder in items]
    return f"You have {len(items)} reminder(s): " + _join_items(parts) + "."


def format_overdue_reminders(reminders: Iterable[Reminder]) -> str:
    items = list(reminders)
    if not items:
        return "You have no overdue reminders."
    parts = [_format_reminder(reminder) for reminder in items]
    return f"You have {len(items)} overdue reminder(s): " + _join_items(parts) + "."


def format_result(result: CalendarQueryResult) -> str:
    """Return a spoken answer for *result* if :attr:`answer` is empty."""
    if result.answer:
        return result.answer

    query_type = result.query.query_type
    if query_type is QueryType.TODAY:
        day = (result.reference or datetime.now()).date()
        return format_day_schedule(
            DaySchedule(day=day, meetings=result.meetings, reminders=result.reminders)
        )
    if query_type is QueryType.TOMORROW:
        day = (result.reference or datetime.now()).date() + timedelta(days=1)
        return format_day_schedule(
            DaySchedule(day=day, meetings=result.meetings, reminders=result.reminders)
        )
    if query_type is QueryType.MEETINGS_THIS_WEEK:
        return format_meetings_this_week(result.meetings)
    if query_type is QueryType.NEXT_MEETING:
        next_meeting = result.meetings[0] if result.meetings else None
        return format_next_meeting(next_meeting)
    if query_type is QueryType.ALL_REMINDERS:
        return format_all_reminders(result.reminders)
    if query_type is QueryType.OVERDUE_REMINDERS:
        return format_overdue_reminders(result.reminders)
    return "I don't know how to answer that calendar question yet."
