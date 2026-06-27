"""Clock-time parsing (24h and 12h) shared across Zara modules."""
from __future__ import annotations

import re
from datetime import datetime, time, timedelta
from typing import Optional

from time_parser.exceptions import TimeParseError

_CLOCK_RE = re.compile(
    r"^\s*(?P<h>\d{1,2})\s*[:.\s]?\s*(?P<m>\d{2})?\s*(?P<ap>am|pm)?\s*$",
    re.IGNORECASE,
)


def parse_clock_time(value: "str | time") -> time:
    """Parse a clock time from a :class:`time` or string (24h or 12h am/pm)."""
    if isinstance(value, time):
        return value
    match = _CLOCK_RE.match(str(value))
    if not match:
        raise TimeParseError(f"Invalid clock time {value!r}; try '07:00' or '7 AM'.")
    hour = int(match.group("h"))
    minute = int(match.group("m") or 0)
    meridiem = (match.group("ap") or "").lower()
    if meridiem == "pm" and hour < 12:
        hour += 12
    elif meridiem == "am" and hour == 12:
        hour = 0
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise TimeParseError(f"Time out of range: {value!r}.")
    return time(hour=hour, minute=minute)


def parse_next_clock_datetime(
    text: str,
    *,
    now: Optional[datetime] = None,
) -> datetime:
    """Parse a clock string into the next future :class:`datetime`.

    If the time already passed today, rolls forward to tomorrow.
    """
    reference = (now or datetime.now()).replace(microsecond=0)
    clock = parse_clock_time(text)
    when = reference.replace(
        hour=clock.hour,
        minute=clock.minute,
        second=0,
        microsecond=0,
    )
    if when <= reference:
        when += timedelta(days=1)
    return when
