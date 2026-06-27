"""Habit domain model and enums."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time
from enum import Enum
from typing import Any, Mapping, Optional

from habits.exceptions import HabitValidationError

from time_parser.clock import parse_clock_time


def parse_time(value: "str | time") -> time:
    """Parses a time from a ``time`` or string (24h or 12h am/pm)."""
    try:
        return parse_clock_time(value)
    except Exception as exc:
        raise HabitValidationError(str(exc)) from exc


class HabitFrequency(str, Enum):
    """How often a habit recurs."""

    DAILY = "daily"
    WEEKDAY = "weekday"   # Mon-Fri
    WEEKEND = "weekend"   # Sat-Sun
    WEEKLY = "weekly"     # once a week (Monday)
    MONTHLY = "monthly"   # once a month (1st)

    @classmethod
    def from_value(cls, value: "str | HabitFrequency") -> "HabitFrequency":
        if isinstance(value, cls):
            return value
        normalised = str(value).strip().lower()
        for member in cls:
            if member.value == normalised:
                return member
        valid = ", ".join(m.value for m in cls)
        raise HabitValidationError(f"Unknown frequency {value!r}. Valid: {valid}.")


class HabitStatus(str, Enum):
    """Lifecycle state of a habit."""

    ACTIVE = "active"
    PAUSED = "paused"

    @classmethod
    def from_value(cls, value: "str | HabitStatus") -> "HabitStatus":
        if isinstance(value, cls):
            return value
        normalised = str(value).strip().lower()
        for member in cls:
            if member.value == normalised:
                return member
        valid = ", ".join(m.value for m in cls)
        raise HabitValidationError(f"Unknown status {value!r}. Valid: {valid}.")


@dataclass
class Habit:
    """A recurring habit.

    Fields: ``id``, ``title``, ``frequency``, ``time``, ``status``, ``streak``,
    ``created_at``.
    """

    title: str
    frequency: HabitFrequency = HabitFrequency.DAILY
    time: time = time(9, 0)
    status: HabitStatus = HabitStatus.ACTIVE
    streak: int = 0
    id: Optional[str] = None
    created_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        if not self.title or not str(self.title).strip():
            raise HabitValidationError("Habit.title must be a non-empty string.")
        self.frequency = HabitFrequency.from_value(self.frequency)
        self.status = HabitStatus.from_value(self.status)
        self.time = parse_time(self.time)
        self.streak = int(self.streak)

    def to_row(self) -> Mapping[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "frequency": self.frequency.value,
            "time": self.time.strftime("%H:%M"),
            "status": self.status.value,
            "streak": self.streak,
            "created_at": (self.created_at or datetime.now()).isoformat(),
        }

    @classmethod
    def from_row(cls, row: Mapping[str, Any]) -> "Habit":
        return cls(
            id=row["id"],
            title=row["title"],
            frequency=HabitFrequency.from_value(row["frequency"]),
            time=parse_time(row["time"]),
            status=HabitStatus.from_value(row["status"]),
            streak=int(row["streak"]),
            created_at=datetime.fromisoformat(row["created_at"]),
        )
