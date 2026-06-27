"""Zara Habit Tracker.

Habits (Drink water, Exercise, Read book, Practice DSA) are stored in SQLite
and scheduled on the shared AutomationEngine so the scheduler automatically
triggers a reminder at each habit's time/frequency.

Public API:
    Habit, HabitFrequency, HabitStatus  -- domain model
    HabitRepository                      -- persistence
    HabitService                         -- create/update/delete/list/mark_done
    HabitConfig                          -- env-driven configuration
"""
from habits.config import HabitConfig
from habits.models import Habit, HabitFrequency, HabitStatus
from habits.repository import HabitRepository
from habits.service import HabitService
from habits.exceptions import (
    HabitError,
    HabitNotFoundError,
    HabitValidationError,
)

__all__ = [
    "HabitConfig",
    "Habit",
    "HabitFrequency",
    "HabitStatus",
    "HabitRepository",
    "HabitService",
    "HabitError",
    "HabitNotFoundError",
    "HabitValidationError",
]
