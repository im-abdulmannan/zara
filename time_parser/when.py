"""Unified datetime parsing: natural language first, clock fallback."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from time_parser.clock import parse_next_clock_datetime
from time_parser.exceptions import TimeParseError
from time_parser.parser import parse_datetime


def parse_when(
    text: str,
    *,
    now: Optional[datetime] = None,
) -> datetime:
    """Parse *text* as NL datetime, falling back to clock time."""
    reference = now or datetime.now()
    cleaned = (text or "").strip()
    if not cleaned:
        raise TimeParseError("Time expression cannot be empty.")
    try:
        return parse_datetime(cleaned, base=reference)
    except TimeParseError:
        return parse_next_clock_datetime(cleaned, now=reference)
