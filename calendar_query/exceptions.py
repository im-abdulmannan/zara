"""Exception hierarchy for the calendar query engine."""
from __future__ import annotations


class CalendarError(Exception):
    """Base class for calendar query errors."""


class CalendarQueryParseError(CalendarError):
    """Raised when a question cannot be mapped to a supported query."""


class CalendarQueryExecutionError(CalendarError):
    """Raised when a query fails during execution."""
