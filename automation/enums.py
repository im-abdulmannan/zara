"""Enumerations describing the kinds of reminders the engine supports."""
from __future__ import annotations

from enum import Enum


class ReminderType(str, Enum):
    """Supported reminder schedule types.

    Subclassing :class:`str` makes values JSON-serialisable and comparable to
    plain strings, which is convenient when specs arrive from the assistant as
    raw text.
    """

    ONE_TIME = "one_time"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    INTERVAL = "interval"

    @classmethod
    def from_value(cls, value: "str | ReminderType") -> "ReminderType":
        """Coerces a string/enum into a :class:`ReminderType`.

        Raises :class:`ValueError` with the list of valid values when unknown.
        """
        if isinstance(value, cls):
            return value
        normalised = str(value).strip().lower()
        for member in cls:
            if member.value == normalised:
                return member
        valid = ", ".join(member.value for member in cls)
        raise ValueError(f"Unknown reminder type {value!r}. Valid values: {valid}.")
