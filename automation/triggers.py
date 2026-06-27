"""Trigger construction strategies.

Each :class:`ReminderType` maps to a :class:`TriggerBuilder` that translates a
schedule payload into a concrete APScheduler trigger. New reminder types can be
supported by implementing a builder and registering it with the
:class:`TriggerFactory` -- the factory and engine stay closed for modification
but open for extension (the "O" in SOLID).
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Mapping, Protocol, runtime_checkable

from apscheduler.triggers.base import BaseTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger

from automation.enums import ReminderType
from automation.exceptions import (
    InvalidScheduleError,
    UnsupportedReminderTypeError,
)

# Keys recognised by the interval reminder.
_INTERVAL_KEYS = ("weeks", "days", "hours", "minutes", "seconds")


def _require(schedule: Mapping[str, Any], *keys: str) -> None:
    """Validates that all ``keys`` are present in ``schedule``.

    Raises:
        InvalidScheduleError: if any required key is missing.
    """
    missing = [key for key in keys if key not in schedule]
    if missing:
        raise InvalidScheduleError(
            f"Schedule is missing required field(s): {', '.join(missing)}."
        )


def _as_int(schedule: Mapping[str, Any], key: str) -> int:
    """Reads an integer schedule field with a clear error on bad input."""
    try:
        return int(schedule[key])
    except (TypeError, ValueError) as exc:
        raise InvalidScheduleError(
            f"Schedule field {key!r} must be an integer, got {schedule[key]!r}."
        ) from exc


def _parse_run_date(value: Any) -> datetime:
    """Parses a one-time run date from a datetime or ISO 8601 string."""
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError as exc:
            raise InvalidScheduleError(
                f"run_date {value!r} is not a valid ISO 8601 datetime."
            ) from exc
    raise InvalidScheduleError(
        f"run_date must be a datetime or ISO 8601 string, got {type(value).__name__}."
    )


@runtime_checkable
class TriggerBuilder(Protocol):
    """Strategy interface: build an APScheduler trigger from a schedule."""

    def build(self, schedule: Mapping[str, Any], timezone: str) -> BaseTrigger:
        """Returns a concrete trigger, or raises :class:`InvalidScheduleError`."""
        ...


class OneTimeTriggerBuilder:
    """Fires once at an absolute datetime.

    Schedule contract: ``{"run_date": datetime | ISO-8601 str}``.
    """

    def build(self, schedule: Mapping[str, Any], timezone: str) -> BaseTrigger:
        _require(schedule, "run_date")
        return DateTrigger(
            run_date=_parse_run_date(schedule["run_date"]),
            timezone=timezone,
        )


class DailyTriggerBuilder:
    """Fires every day at a fixed time.

    Schedule contract: ``{"hour": int, "minute": int}``.
    """

    def build(self, schedule: Mapping[str, Any], timezone: str) -> BaseTrigger:
        _require(schedule, "hour", "minute")
        return CronTrigger(
            hour=_as_int(schedule, "hour"),
            minute=_as_int(schedule, "minute"),
            timezone=timezone,
        )


class WeeklyTriggerBuilder:
    """Fires on given weekday(s) at a fixed time.

    Schedule contract: ``{"day_of_week": str | int, "hour": int, "minute": int}``.
    ``day_of_week`` accepts APScheduler syntax (e.g. ``"mon"``, ``"mon-fri"``,
    ``"0"``).
    """

    def build(self, schedule: Mapping[str, Any], timezone: str) -> BaseTrigger:
        _require(schedule, "day_of_week", "hour", "minute")
        return CronTrigger(
            day_of_week=schedule["day_of_week"],
            hour=_as_int(schedule, "hour"),
            minute=_as_int(schedule, "minute"),
            timezone=timezone,
        )


class MonthlyTriggerBuilder:
    """Fires on a given day of the month at a fixed time.

    Schedule contract: ``{"day": int, "hour": int, "minute": int}``.
    """

    def build(self, schedule: Mapping[str, Any], timezone: str) -> BaseTrigger:
        _require(schedule, "day", "hour", "minute")
        return CronTrigger(
            day=_as_int(schedule, "day"),
            hour=_as_int(schedule, "hour"),
            minute=_as_int(schedule, "minute"),
            timezone=timezone,
        )


class IntervalTriggerBuilder:
    """Fires repeatedly on a fixed interval.

    Schedule contract: at least one of ``weeks/days/hours/minutes/seconds``
    (ints). Example: ``{"minutes": 30}``.
    """

    def build(self, schedule: Mapping[str, Any], timezone: str) -> BaseTrigger:
        kwargs = {key: _as_int(schedule, key) for key in _INTERVAL_KEYS if key in schedule}
        if not kwargs:
            raise InvalidScheduleError(
                "Interval schedule needs at least one of: "
                + ", ".join(_INTERVAL_KEYS)
                + "."
            )
        if all(value <= 0 for value in kwargs.values()):
            raise InvalidScheduleError("Interval must be greater than zero.")
        return IntervalTrigger(timezone=timezone, **kwargs)


def default_builders() -> Dict[ReminderType, TriggerBuilder]:
    """Returns the built-in mapping of reminder type to trigger builder."""
    return {
        ReminderType.ONE_TIME: OneTimeTriggerBuilder(),
        ReminderType.DAILY: DailyTriggerBuilder(),
        ReminderType.WEEKLY: WeeklyTriggerBuilder(),
        ReminderType.MONTHLY: MonthlyTriggerBuilder(),
        ReminderType.INTERVAL: IntervalTriggerBuilder(),
    }


class TriggerFactory:
    """Resolves a reminder type to a trigger via its registered builder."""

    def __init__(
        self,
        builders: Dict[ReminderType, TriggerBuilder] | None = None,
    ) -> None:
        self._builders: Dict[ReminderType, TriggerBuilder] = (
            builders if builders is not None else default_builders()
        )

    def register(self, reminder_type: ReminderType, builder: TriggerBuilder) -> None:
        """Registers (or overrides) the builder for a reminder type."""
        self._builders[reminder_type] = builder

    def create(
        self,
        reminder_type: ReminderType,
        schedule: Mapping[str, Any],
        timezone: str,
    ) -> BaseTrigger:
        """Builds the trigger for ``reminder_type``.

        Raises:
            UnsupportedReminderTypeError: if no builder is registered.
            InvalidScheduleError: if the schedule payload is invalid.
        """
        builder = self._builders.get(reminder_type)
        if builder is None:
            raise UnsupportedReminderTypeError(
                f"No trigger builder registered for {reminder_type.value!r}."
            )
        return builder.build(schedule, timezone)
