"""Reminder domain model and enums.

This module has no dependencies on persistence or scheduling -- it is the pure
domain layer that everything else is built around.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Mapping, Optional


class RepeatType(str, Enum):
    """How often a reminder recurs."""

    ONCE = "once"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"

    @classmethod
    def from_value(cls, value: "str | RepeatType") -> "RepeatType":
        if isinstance(value, cls):
            return value
        normalised = str(value).strip().lower()
        for member in cls:
            if member.value == normalised:
                return member
        valid = ", ".join(m.value for m in cls)
        raise ValueError(f"Unknown repeat_type {value!r}. Valid: {valid}.")


class ReminderStatus(str, Enum):
    """Lifecycle state of a reminder."""

    SCHEDULED = "scheduled"   # active and awaiting its next run
    PAUSED = "paused"         # temporarily suspended
    COMPLETED = "completed"   # a one-time reminder that has fired
    CANCELLED = "cancelled"   # cancelled by the user

    @classmethod
    def from_value(cls, value: "str | ReminderStatus") -> "ReminderStatus":
        if isinstance(value, cls):
            return value
        normalised = str(value).strip().lower()
        for member in cls:
            if member.value == normalised:
                return member
        valid = ", ".join(m.value for m in cls)
        raise ValueError(f"Unknown status {value!r}. Valid: {valid}.")


@dataclass
class Reminder:
    """A single reminder.

    Fields (as required): ``id``, ``title``, ``description``, ``datetime``,
    ``repeat_type``, ``status``, ``created_at``.

    Note:
        The due-time attribute is exposed as ``remind_at`` in Python to avoid
        shadowing the stdlib :class:`datetime.datetime` type, but it is stored
        in (and round-trips through) the ``datetime`` SQLite column. Use
        :attr:`datetime` as a read alias if you prefer the spec name.
    """

    title: str
    remind_at: datetime
    description: str = ""
    repeat_type: RepeatType = RepeatType.ONCE
    status: ReminderStatus = ReminderStatus.SCHEDULED
    id: Optional[str] = None
    created_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        self.repeat_type = RepeatType.from_value(self.repeat_type)
        self.status = ReminderStatus.from_value(self.status)
        if not self.title or not str(self.title).strip():
            raise ValueError("Reminder.title must be a non-empty string.")
        if not isinstance(self.remind_at, datetime):
            raise ValueError("Reminder.remind_at must be a datetime.")

    @property
    def datetime(self) -> datetime:  # noqa: A003 -- spec field name alias
        """Spec-named read alias for :attr:`remind_at`."""
        return self.remind_at

    def to_row(self) -> Mapping[str, Any]:
        """Serialises the reminder into a dict of SQLite column values."""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "datetime": self.remind_at.isoformat(),
            "repeat_type": self.repeat_type.value,
            "status": self.status.value,
            "created_at": (self.created_at or datetime.now()).isoformat(),
        }

    @classmethod
    def from_row(cls, row: Mapping[str, Any]) -> "Reminder":
        """Reconstructs a reminder from a SQLite row mapping."""
        return cls(
            id=row["id"],
            title=row["title"],
            description=row["description"] or "",
            remind_at=datetime.fromisoformat(row["datetime"]),
            repeat_type=RepeatType.from_value(row["repeat_type"]),
            status=ReminderStatus.from_value(row["status"]),
            created_at=datetime.fromisoformat(row["created_at"]),
        )
