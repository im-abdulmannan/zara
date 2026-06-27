"""Exception hierarchy for the reminder service.

Mirrors the pattern used by the automation package: a single base class lets
callers catch broadly, while specific subclasses allow targeted handling.
"""
from __future__ import annotations


class ReminderError(Exception):
    """Base class for all reminder service errors."""


class ReminderNotFoundError(ReminderError):
    """Raised when a reminder id does not exist in the repository."""


class ReminderValidationError(ReminderError):
    """Raised when reminder input data is invalid."""
