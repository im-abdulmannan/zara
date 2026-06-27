"""Zara Natural Language Time Parser.

Parses phrases like "tomorrow", "next Friday", "in 2 hours", and
"every Monday" into :class:`datetime.datetime` objects using dateparser.

Public API:
    parse_natural_time  -- full parse result with optional recurrence
    parse_datetime      -- convenience wrapper returning datetime only
    NaturalLanguageTimeParser
    ParsedDateTime, RecurrenceRule, RecurrenceKind
"""
from time_parser.clock import parse_clock_time, parse_next_clock_datetime
from time_parser.when import parse_when
from time_parser.patterns import looks_like_timed_reminder, TIME_EXPRESSION_RE
from time_parser.parser import (
    NaturalLanguageTimeParser,
    get_parser,
    parse_datetime,
    parse_natural_time,
)
from time_parser.config import TimeParserConfig
from time_parser.models import ParsedDateTime, RecurrenceKind, RecurrenceRule
from time_parser.exceptions import (
    TimeParserError,
    TimeParseError,
    TimeValidationError,
)

__all__ = [
    "NaturalLanguageTimeParser",
    "TimeParserConfig",
    "ParsedDateTime",
    "RecurrenceRule",
    "RecurrenceKind",
    "parse_natural_time",
    "parse_datetime",
    "parse_when",
    "parse_clock_time",
    "parse_next_clock_datetime",
    "looks_like_timed_reminder",
    "TIME_EXPRESSION_RE",
    "get_parser",
    "TimeParserError",
    "TimeParseError",
    "TimeValidationError",
]
