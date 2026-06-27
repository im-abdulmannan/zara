"""Domain models for parsed natural-language times."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


class RecurrenceKind(str, Enum):
    """Supported recurrence patterns."""

    ONCE = "once"
    WEEKLY = "weekly"
    WEEKDAY = "weekday"
    WEEKEND = "weekend"
    MONTHLY = "monthly"
    YEARLY = "yearly"

    @classmethod
    def from_value(cls, value: "str | RecurrenceKind") -> "RecurrenceKind":
        if isinstance(value, cls):
            return value
        normalised = str(value).strip().lower()
        for member in cls:
            if member.value == normalised:
                return member
        return cls.ONCE


@dataclass(frozen=True)
class RecurrenceRule:
    """Recurrence metadata extracted from a phrase like 'every Monday'."""

    kind: RecurrenceKind
    weekday: Optional[int] = None  # 0=Monday .. 6=Sunday (for WEEKLY)

    def __post_init__(self) -> None:
        if self.weekday is not None and not (0 <= self.weekday <= 6):
            raise ValueError("weekday must be between 0 (Monday) and 6 (Sunday).")


@dataclass(frozen=True)
class ParsedDateTime:
    """Result of parsing a natural-language time expression."""

    dt: datetime
    raw_text: str
    recurrence: Optional[RecurrenceRule] = None

    @property
    def datetime(self) -> datetime:
        """Alias for :attr:`dt` (spec-friendly name)."""
        return self.dt

    @property
    def is_recurring(self) -> bool:
        return self.recurrence is not None and self.recurrence.kind is not RecurrenceKind.ONCE
