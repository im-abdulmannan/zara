"""Tests for reminder persistence and scheduling."""
from __future__ import annotations

from datetime import datetime, timedelta

from reminders.models import ReminderStatus


def test_create_reminder(zara_runtime):
    when = datetime.now() + timedelta(hours=1)
    reminder = zara_runtime.schedule_reminder("call mom", when=when)
    assert reminder.title == "call mom"
    assert reminder.status is ReminderStatus.SCHEDULED


def test_list_active_reminders(zara_runtime):
    when = datetime.now() + timedelta(hours=2)
    zara_runtime.schedule_reminder("meeting prep", when=when)
    active = zara_runtime.active_reminders()
    assert any(r.title == "meeting prep" for r in active)


def test_cancel_reminder(zara_runtime):
    when = datetime.now() + timedelta(hours=3)
    reminder = zara_runtime.schedule_reminder("temp task", when=when)
    zara_runtime.cancel_reminder(reminder.id)
    active = zara_runtime.active_reminders()
    assert all(r.id != reminder.id for r in active)
