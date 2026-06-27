"""Zara Calendar Query Engine.

Answers natural-language questions about meetings and reminders.

Public API:
    CalendarQueryEngine   -- parse and execute calendar questions
    query_calendar        -- convenience function
    parse_calendar_question
    CalendarQuery, CalendarQueryResult, QueryType
"""
from calendar_query.engine import (
    CalendarQueryEngine,
    get_engine,
    query_calendar,
)
from calendar_query.parser import parse_calendar_question
from calendar_query.config import CalendarConfig
from calendar_query.models import (
    CalendarQuery,
    CalendarQueryResult,
    DaySchedule,
    QueryType,
)
from calendar_query.exceptions import (
    CalendarError,
    CalendarQueryParseError,
    CalendarQueryExecutionError,
)

__all__ = [
    "CalendarQueryEngine",
    "CalendarConfig",
    "CalendarQuery",
    "CalendarQueryResult",
    "DaySchedule",
    "QueryType",
    "parse_calendar_question",
    "query_calendar",
    "get_engine",
    "CalendarError",
    "CalendarQueryParseError",
    "CalendarQueryExecutionError",
]
