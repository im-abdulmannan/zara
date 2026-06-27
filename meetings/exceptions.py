"""Exception hierarchy for the meeting manager."""
from __future__ import annotations


class MeetingError(Exception):
    """Base class for all meeting manager errors."""


class MeetingNotFoundError(MeetingError):
    """Raised when a meeting id does not exist."""


class MeetingValidationError(MeetingError):
    """Raised when meeting input data is invalid."""
