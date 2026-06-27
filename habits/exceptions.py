"""Exception hierarchy for the habit tracker."""
from __future__ import annotations


class HabitError(Exception):
    """Base class for all habit tracker errors."""


class HabitNotFoundError(HabitError):
    """Raised when a habit id does not exist."""


class HabitValidationError(HabitError):
    """Raised when habit input data is invalid."""
