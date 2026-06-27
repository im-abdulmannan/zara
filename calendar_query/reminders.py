"""Reminder scheduling helpers for calendar queries."""
from __future__ import annotations

from datetime import date, datetime, time
from typing import Iterable, List

from reminders.models import Reminder, ReminderStatus, RepeatType


def is_active_reminder(reminder: Reminder) -> bool:
    """Return True if the reminder should appear in calendar listings."""
    return reminder.status in (ReminderStatus.SCHEDULED, ReminderStatus.PAUSED)


def reminder_occurs_on(reminder: Reminder, day: date) -> bool:
    """Return True if *reminder* fires on *day* based on its repeat rule."""
    if not is_active_reminder(reminder):
        return False

    repeat = reminder.repeat_type
    anchor = reminder.remind_at.date()

    if repeat is RepeatType.ONCE:
        return anchor == day
    if repeat is RepeatType.DAILY:
        return day >= anchor
    if repeat is RepeatType.WEEKLY:
        return day >= anchor and day.weekday() == anchor.weekday()
    if repeat is RepeatType.MONTHLY:
        if day < anchor.replace(day=1):
            return False
        try:
            return day.day == anchor.day
        except ValueError:
            return False
    return False


def reminder_display_time(reminder: Reminder, day: date) -> datetime:
    """Return the clock time for *reminder* on *day*."""
    anchor = reminder.remind_at
    return datetime.combine(day, anchor.time())


def filter_reminders_for_day(
    reminders: Iterable[Reminder],
    day: date,
) -> List[Reminder]:
    """Return active reminders that occur on *day*, sorted by time."""
    matched = [r for r in reminders if reminder_occurs_on(r, day)]
    return sorted(matched, key=lambda r: reminder_display_time(r, day))


def filter_overdue_reminders(
    reminders: Iterable[Reminder],
    *,
    now: datetime | None = None,
) -> List[Reminder]:
    """Return scheduled reminders whose due time is in the past."""
    reference = now or datetime.now()
    overdue = [
        r
        for r in reminders
        if r.status is ReminderStatus.SCHEDULED and r.remind_at < reference
    ]
    return sorted(overdue, key=lambda r: r.remind_at)


def filter_all_listable_reminders(reminders: Iterable[Reminder]) -> List[Reminder]:
    """Return non-cancelled, non-completed reminders sorted by due time."""
    visible_statuses = {ReminderStatus.SCHEDULED, ReminderStatus.PAUSED}
    matched = [r for r in reminders if r.status in visible_statuses]
    return sorted(matched, key=lambda r: r.remind_at)
