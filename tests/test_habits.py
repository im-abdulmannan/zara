"""Tests for habit tracking."""
from __future__ import annotations

from habits.models import HabitStatus


def test_create_habit(zara_runtime):
    habit = zara_runtime.create_habit("drink water", frequency="daily", at_time="09:00")
    assert habit.title == "drink water"
    assert habit.status is HabitStatus.ACTIVE


def test_list_active_habits(zara_runtime):
    zara_runtime.create_habit("meditate", at_time="08:00")
    habits = zara_runtime.active_habits()
    assert any(h.title == "meditate" for h in habits)


def test_mark_habit_done_increments_streak(zara_runtime):
    habit = zara_runtime.create_habit("stretch", at_time="07:00")
    updated = zara_runtime.mark_habit_done(habit.id)
    assert updated.streak >= 1


def test_pause_and_resume_habit(zara_runtime):
    habit = zara_runtime.create_habit("read", at_time="21:00")
    paused = zara_runtime.pause_habit(habit.id)
    assert paused.status is HabitStatus.PAUSED
    resumed = zara_runtime.resume_habit(habit.id)
    assert resumed.status is HabitStatus.ACTIVE


def test_delete_habit(zara_runtime):
    habit = zara_runtime.create_habit("journal", at_time="22:00")
    zara_runtime.delete_habit(habit.id)
    assert all(h.id != habit.id for h in zara_runtime.all_habits())
