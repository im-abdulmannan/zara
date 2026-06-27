"""Exception hierarchy for the natural-language time parser."""
from __future__ import annotations


class TimeParserError(Exception):
    """Base class for time parser errors."""


class TimeParseError(TimeParserError):
    """Raised when a time expression cannot be parsed."""


class TimeValidationError(TimeParserError):
    """Raised when parsed time data is invalid."""
