"""Natural-language question parser for calendar queries."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Sequence

from calendar_query.models import CalendarQuery, QueryType

_NORMALISE_RE = re.compile(r"[^\w\s']+")
_COLLAPSE_SPACE = re.compile(r"\s+")


@dataclass(frozen=True)
class _QueryPattern:
    query_type: QueryType
    patterns: Sequence[str]
    confidence: float = 1.0


_QUERY_PATTERNS: tuple[_QueryPattern, ...] = (
    _QueryPattern(
        QueryType.OVERDUE_REMINDERS,
        (
            r"show overdue reminders",
            r"overdue reminders",
            r"any overdue reminders",
            r"list overdue reminders",
            r"what reminders are overdue",
            r"do i have overdue reminders",
        ),
    ),
    _QueryPattern(
        QueryType.ALL_REMINDERS,
        (
            r"show all reminders",
            r"list all reminders",
            r"list reminders",
            r"show reminders",
            r"what are my reminders",
            r"my reminders",
            r"all my reminders",
        ),
    ),
    _QueryPattern(
        QueryType.NEXT_MEETING,
        (
            r"when is my next meeting",
            r"what is my next meeting",
            r"what'?s my next meeting",
            r"next meeting",
            r"when'?s my next meeting",
        ),
    ),
    _QueryPattern(
        QueryType.MEETINGS_THIS_WEEK,
        (
            r"do i have meetings this week",
            r"any meetings this week",
            r"meetings this week",
            r"what meetings do i have this week",
            r"show meetings this week",
            r"my meetings this week",
        ),
    ),
    _QueryPattern(
        QueryType.TODAY,
        (
            r"what do i have today",
            r"what'?s on today",
            r"whats on today",
            r"what is on today",
            r"my schedule today",
            r"what do i have on today",
            r"what'?s on my calendar today",
            r"what is on my calendar today",
            r"what do i have scheduled today",
        ),
    ),
    _QueryPattern(
        QueryType.TOMORROW,
        (
            r"what do i have tomorrow",
            r"what'?s on tomorrow",
            r"whats on tomorrow",
            r"what is on tomorrow",
            r"my schedule tomorrow",
            r"what do i have on tomorrow",
            r"what'?s on my calendar tomorrow",
            r"what is on my calendar tomorrow",
            r"what do i have scheduled tomorrow",
        ),
    ),
)

_COMPILED: tuple[tuple[QueryType, re.Pattern[str], float], ...] = tuple(
    (entry.query_type, re.compile(pattern, re.IGNORECASE), entry.confidence)
    for entry in _QUERY_PATTERNS
    for pattern in entry.patterns
)


def _normalise_question(text: str) -> str:
    cleaned = text.strip().lower()
    cleaned = _NORMALISE_RE.sub(" ", cleaned)
    cleaned = _COLLAPSE_SPACE.sub(" ", cleaned).strip()
    return cleaned


def parse_calendar_question(text: str) -> CalendarQuery:
    """Map *text* to a supported :class:`CalendarQuery`."""
    raw = (text or "").strip()
    if not raw:
        return CalendarQuery(
            query_type=QueryType.UNKNOWN,
            question=raw,
            confidence=0.0,
        )

    normalised = _normalise_question(raw)
    for query_type, pattern, confidence in _COMPILED:
        if pattern.search(normalised):
            return CalendarQuery(
                query_type=query_type,
                question=raw,
                confidence=confidence,
            )

    return CalendarQuery(
        query_type=QueryType.UNKNOWN,
        question=raw,
        confidence=0.0,
    )
