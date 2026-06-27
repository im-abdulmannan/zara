"""Domain-specific exceptions for the automation engine.

A dedicated exception hierarchy lets callers catch :class:`AutomationError`
broadly or handle specific failure modes, instead of leaking APScheduler's
internal exception types across the package boundary.
"""
from __future__ import annotations


class AutomationError(Exception):
    """Base class for all automation engine errors."""


class SchedulerNotRunningError(AutomationError):
    """Raised when an operation requires a started scheduler but it is not running."""


class JobNotFoundError(AutomationError):
    """Raised when a referenced job id does not exist."""


class DuplicateJobError(AutomationError):
    """Raised when creating a job whose id already exists."""


class InvalidScheduleError(AutomationError):
    """Raised when a schedule payload is missing fields or has invalid values."""


class UnsupportedReminderTypeError(AutomationError):
    """Raised when no trigger builder is registered for a reminder type."""
