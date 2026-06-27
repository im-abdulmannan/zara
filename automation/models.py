"""Data models exchanged across the automation engine boundary.

``JobSpec`` is the input contract (what the assistant asks to schedule) and
``JobInfo`` is the output contract (a serialisable snapshot of a scheduled
job). Keeping these as explicit, typed structures decouples callers from
APScheduler's ``Job`` object.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping, Optional

from automation.enums import ReminderType


@dataclass
class JobSpec:
    """Description of a reminder to schedule.

    Attributes:
        name: Human-readable label for the reminder.
        message: Text delivered to handlers when the reminder fires.
        reminder_type: Which schedule strategy to use.
        schedule: Trigger parameters; required keys depend on ``reminder_type``
            (see the trigger builders for each type's contract).
        job_id: Optional explicit id; a UUID is generated when omitted.
        metadata: Arbitrary extra data passed through to handlers. Must contain
            only pickle-serialisable values when a persistent job store is used.
    """

    name: str
    message: str
    reminder_type: ReminderType
    schedule: Mapping[str, Any]
    job_id: Optional[str] = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Coerce a raw string reminder type into the enum so callers can pass
        # either form without the engine having to special-case it.
        self.reminder_type = ReminderType.from_value(self.reminder_type)
        if not self.name or not str(self.name).strip():
            raise ValueError("JobSpec.name must be a non-empty string.")
        if not isinstance(self.schedule, Mapping):
            raise ValueError("JobSpec.schedule must be a mapping.")


@dataclass(frozen=True)
class JobInfo:
    """Immutable snapshot of a scheduled job, safe to serialise and display."""

    job_id: str
    name: str
    message: Optional[str]
    reminder_type: Optional[str]
    trigger: str
    next_run_time: Optional[datetime]
    paused: bool

    def to_dict(self) -> dict[str, Any]:
        """Returns a JSON-friendly representation (datetimes as ISO strings)."""
        return {
            "job_id": self.job_id,
            "name": self.name,
            "message": self.message,
            "reminder_type": self.reminder_type,
            "trigger": self.trigger,
            "next_run_time": (
                self.next_run_time.isoformat() if self.next_run_time else None
            ),
            "paused": self.paused,
        }
