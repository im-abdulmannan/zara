"""Natural-language time parser powered by dateparser."""
from __future__ import annotations

import re
from datetime import datetime, time, timedelta
from typing import Optional

import dateparser
from dateutil.relativedelta import relativedelta

from time_parser.config import TimeParserConfig
from time_parser.exceptions import TimeParseError
from time_parser.logging_config import get_logger
from time_parser.models import ParsedDateTime, RecurrenceKind, RecurrenceRule

_WEEKDAY_NAMES: dict[str, int] = {
    "monday": 0,
    "monday's": 0,
    "mon": 0,
    "tuesday": 1,
    "tuesday's": 1,
    "tue": 1,
    "tues": 1,
    "wednesday": 2,
    "wednesday's": 2,
    "wed": 2,
    "thursday": 3,
    "thursday's": 3,
    "thu": 3,
    "thur": 3,
    "thurs": 3,
    "friday": 4,
    "friday's": 4,
    "fri": 4,
    "saturday": 5,
    "saturday's": 5,
    "sat": 5,
    "sunday": 6,
    "sunday's": 6,
    "sun": 6,
}

_RECURRENCE_PATTERNS: tuple[tuple[re.Pattern[str], RecurrenceKind], ...] = (
    (re.compile(r"\bevery\s+weekdays?\b", re.IGNORECASE), RecurrenceKind.WEEKDAY),
    (re.compile(r"\bevery\s+weekends?\b", re.IGNORECASE), RecurrenceKind.WEEKEND),
    (re.compile(r"\bevery\s+month(?:ly)?\b", re.IGNORECASE), RecurrenceKind.MONTHLY),
    (re.compile(r"\bevery\s+year(?:ly)?\b", re.IGNORECASE), RecurrenceKind.YEARLY),
)

_EVERY_WEEKDAY_PATTERN = re.compile(
    r"\bevery\s+(?P<day>"
    + "|".join(re.escape(name) for name in sorted(_WEEKDAY_NAMES, key=len, reverse=True))
    + r")\b",
    re.IGNORECASE,
)

_NEXT_WEEKDAY_PATTERN = re.compile(
    r"\bnext\s+(?P<day>"
    + "|".join(re.escape(name) for name in sorted(_WEEKDAY_NAMES, key=len, reverse=True))
    + r")\b",
    re.IGNORECASE,
)

_THIS_WEEKDAY_PATTERN = re.compile(
    r"\bthis\s+(?P<day>"
    + "|".join(re.escape(name) for name in sorted(_WEEKDAY_NAMES, key=len, reverse=True))
    + r")\b",
    re.IGNORECASE,
)

_ON_WEEKDAY_PATTERN = re.compile(
    r"\bon\s+(?P<day>"
    + "|".join(re.escape(name) for name in sorted(_WEEKDAY_NAMES, key=len, reverse=True))
    + r")\b",
    re.IGNORECASE,
)

_STRIP_TOKENS = re.compile(
    r"\b(?:at|on|by|@)\b",
    re.IGNORECASE,
)

_COLLAPSE_SPACE = re.compile(r"\s+")


def _normalize_text(text: str) -> str:
    cleaned = text.strip()
    cleaned = _STRIP_TOKENS.sub(" ", cleaned)
    cleaned = _COLLAPSE_SPACE.sub(" ", cleaned).strip()
    return cleaned


def _weekday_index(name: str) -> int:
    key = name.lower().strip()
    if key not in _WEEKDAY_NAMES:
        raise TimeParseError(f"Unknown weekday {name!r}.")
    return _WEEKDAY_NAMES[key]


def _replace_match(text: str, match: re.Match[str], replacement: str = " ") -> str:
    start, end = match.span()
    return (text[:start] + replacement + text[end:]).strip()


def _extract_recurrence(text: str) -> tuple[str, Optional[RecurrenceRule]]:
    for pattern, kind in _RECURRENCE_PATTERNS:
        match = pattern.search(text)
        if match:
            remainder = _replace_match(text, match)
            return remainder, RecurrenceRule(kind=kind)

    match = _EVERY_WEEKDAY_PATTERN.search(text)
    if match:
        weekday = _weekday_index(match.group("day"))
        remainder = _replace_match(text, match)
        return remainder, RecurrenceRule(kind=RecurrenceKind.WEEKLY, weekday=weekday)

    return text, None


def _extract_next_weekday(text: str) -> tuple[str, Optional[int]]:
    match = _NEXT_WEEKDAY_PATTERN.search(text)
    if match:
        weekday = _weekday_index(match.group("day"))
        remainder = _replace_match(text, match)
        return remainder, weekday
    return text, None


def _extract_this_weekday(text: str) -> tuple[str, Optional[int]]:
    match = _THIS_WEEKDAY_PATTERN.search(text)
    if match:
        weekday = _weekday_index(match.group("day"))
        remainder = _replace_match(text, match)
        return remainder, weekday
    return text, None


def _extract_on_weekday(text: str) -> tuple[str, Optional[int]]:
    match = _ON_WEEKDAY_PATTERN.search(text)
    if match:
        weekday = _weekday_index(match.group("day"))
        remainder = _replace_match(text, match)
        return remainder, weekday
    return text, None


def _dateparser_settings(base: datetime) -> dict:
    return {
        "RELATIVE_BASE": base,
        "PREFER_DATES_FROM": "future",
        "RETURN_AS_TIMEZONE_AWARE": False,
        "PARSERS": [
            "relative-time",
            "absolute-time",
            "timestamp",
            "custom-formats",
        ],
        "TIMEZONE": "local",
    }


def _parse_with_dateparser(text: str, base: datetime) -> Optional[datetime]:
    if not text:
        return None
    return dateparser.parse(text, settings=_dateparser_settings(base))


def _apply_time_to_date(
    target_date: datetime,
    parsed: Optional[datetime],
    *,
    default_time: time,
    base: datetime,
) -> datetime:
    if parsed is None:
        hour = default_time.hour
        minute = default_time.minute
        second = default_time.second
        microsecond = default_time.microsecond
    elif (
        parsed.date() == base.date()
        and parsed.time() != time(0, 0)
        and parsed.hour == base.hour
        and parsed.minute == base.minute
        and parsed.second == base.second
    ):
        # dateparser often returns RELATIVE_BASE when only a weekday was given.
        hour = default_time.hour
        minute = default_time.minute
        second = default_time.second
        microsecond = default_time.microsecond
    elif parsed.time() != time(0, 0) or parsed.date() != base.date():
        hour = parsed.hour
        minute = parsed.minute
        second = parsed.second
        microsecond = parsed.microsecond
    else:
        hour = default_time.hour
        minute = default_time.minute
        second = default_time.second
        microsecond = default_time.microsecond

    return target_date.replace(
        hour=hour,
        minute=minute,
        second=second,
        microsecond=microsecond,
    )


def _next_weekday(
    base: datetime,
    weekday: int,
    *,
    include_today: bool = False,
    force_next_week: bool = False,
) -> datetime:
    days_ahead = weekday - base.weekday()
    if force_next_week:
        if days_ahead <= 0:
            days_ahead += 7
        elif base.weekday() == weekday:
            days_ahead = 7
    elif include_today:
        if days_ahead < 0:
            days_ahead += 7
    else:
        if days_ahead <= 0:
            days_ahead += 7
    return (base + timedelta(days=days_ahead)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )


def _next_weekday_recurrence(base: datetime) -> datetime:
    if base.weekday() < 5:
        target = base.replace(hour=0, minute=0, second=0, microsecond=0)
        if base.weekday() == 4:
            # Friday -> next Monday
            target = _next_weekday(base, 0)
        return target
    # Saturday -> Monday; Sunday -> Monday
    return _next_weekday(base, 0)


def _next_weekend_recurrence(base: datetime) -> datetime:
    weekday = base.weekday()
    if weekday == 5:
        return base.replace(hour=0, minute=0, second=0, microsecond=0)
    if weekday == 6:
        return base.replace(hour=0, minute=0, second=0, microsecond=0)
    # Mon-Fri -> upcoming Saturday
    return _next_weekday(base, 5)


def _next_monthly(base: datetime) -> datetime:
    anchor = base.replace(hour=0, minute=0, second=0, microsecond=0)
    candidate = anchor + relativedelta(months=1)
    if candidate <= base:
        candidate = anchor + relativedelta(months=1)
    return candidate


def _next_yearly(base: datetime) -> datetime:
    anchor = base.replace(hour=0, minute=0, second=0, microsecond=0)
    candidate = anchor + relativedelta(years=1)
    if candidate <= base:
        candidate = anchor + relativedelta(years=1)
    return candidate


def _resolve_recurrence_date(
    base: datetime,
    rule: RecurrenceRule,
) -> datetime:
    if rule.kind is RecurrenceKind.WEEKLY:
        if rule.weekday is None:
            raise TimeParseError("Weekly recurrence requires a weekday.")
        return _next_weekday(base, rule.weekday)
    if rule.kind is RecurrenceKind.WEEKDAY:
        return _next_weekday_recurrence(base)
    if rule.kind is RecurrenceKind.WEEKEND:
        return _next_weekend_recurrence(base)
    if rule.kind is RecurrenceKind.MONTHLY:
        return _next_monthly(base)
    if rule.kind is RecurrenceKind.YEARLY:
        return _next_yearly(base)
    raise TimeParseError(f"Unsupported recurrence kind {rule.kind!r}.")


def _ensure_future(
    dt: datetime,
    base: datetime,
    *,
    recurrence: Optional[RecurrenceRule],
    parsed_fragment: Optional[datetime],
    default_time: time,
) -> datetime:
    if dt > base:
        return dt

    if recurrence is None:
        return dt + timedelta(days=1)

    if recurrence.kind is RecurrenceKind.WEEKEND and base.weekday() == 5:
        sunday = (base + timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        dt = _apply_time_to_date(
            sunday,
            parsed_fragment,
            default_time=default_time,
            base=base,
        )
        if dt > base:
            return dt

    next_base = base + timedelta(days=1)
    anchor = _resolve_recurrence_date(next_base, recurrence)
    return _apply_time_to_date(
        anchor,
        parsed_fragment,
        default_time=default_time,
        base=base,
    )


class NaturalLanguageTimeParser:
    """Parses natural-language time expressions into :class:`datetime` values."""

    def __init__(self, config: TimeParserConfig | None = None) -> None:
        self._config = config or TimeParserConfig.from_env()
        self._logger = get_logger(__name__, self._config.log_level)

    @property
    def config(self) -> TimeParserConfig:
        return self._config

    def parse(
        self,
        text: str,
        *,
        base: datetime | None = None,
    ) -> ParsedDateTime:
        """Parse *text* into a :class:`ParsedDateTime`."""
        raw_text = (text or "").strip()
        if not raw_text:
            raise TimeParseError("Time expression cannot be empty.")

        reference = base or datetime.now()
        reference = reference.replace(microsecond=0)

        working = _normalize_text(raw_text)

        working, recurrence = _extract_recurrence(working)
        working, next_weekday = _extract_next_weekday(working)
        working, this_weekday = _extract_this_weekday(working)
        working, on_weekday = _extract_on_weekday(working)

        parsed_fragment = _parse_with_dateparser(working, reference)

        anchor_date: datetime | None = None
        force_next_week = next_weekday is not None

        if next_weekday is not None:
            anchor_date = _next_weekday(
                reference,
                next_weekday,
                force_next_week=True,
            )
        elif this_weekday is not None:
            anchor_date = _next_weekday(
                reference,
                this_weekday,
                include_today=True,
            )
        elif on_weekday is not None:
            anchor_date = _next_weekday(reference, on_weekday)
        elif recurrence is not None:
            anchor_date = _resolve_recurrence_date(reference, recurrence)

        if anchor_date is not None:
            dt = _apply_time_to_date(
                anchor_date,
                parsed_fragment,
                default_time=self._config.default_time,
                base=reference,
            )
        elif parsed_fragment is not None:
            dt = parsed_fragment.replace(microsecond=0)
        else:
            raise TimeParseError(f"Could not parse time expression: {raw_text!r}")

        dt = _ensure_future(
            dt,
            reference,
            recurrence=recurrence,
            parsed_fragment=parsed_fragment,
            default_time=self._config.default_time,
        )

        result = ParsedDateTime(
            dt=dt,
            raw_text=raw_text,
            recurrence=recurrence,
        )
        self._logger.debug(
            "Parsed %r -> %s (recurrence=%s)",
            raw_text,
            dt.isoformat(sep=" "),
            recurrence,
        )
        return result

    def parse_datetime(
        self,
        text: str,
        *,
        base: datetime | None = None,
    ) -> datetime:
        """Parse *text* and return only the resolved :class:`datetime`."""
        return self.parse(text, base=base).dt


_default_parser: NaturalLanguageTimeParser | None = None


def get_parser() -> NaturalLanguageTimeParser:
    """Return the process-wide singleton parser."""
    global _default_parser
    if _default_parser is None:
        _default_parser = NaturalLanguageTimeParser()
    return _default_parser


def parse_natural_time(
    text: str,
    *,
    base: datetime | None = None,
) -> ParsedDateTime:
    """Parse *text* using the shared parser instance."""
    return get_parser().parse(text, base=base)


def parse_datetime(
    text: str,
    *,
    base: datetime | None = None,
) -> datetime:
    """Parse *text* and return a :class:`datetime` (convenience wrapper)."""
    return get_parser().parse_datetime(text, base=base)
