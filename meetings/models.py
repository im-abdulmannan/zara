"""Meeting domain model + date/time parsing helpers."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Any, List, Mapping, Optional

from meetings.exceptions import MeetingValidationError
from time_parser.clock import parse_clock_time


def parse_date(value: "str | date | datetime", today: Optional[date] = None) -> date:
    """Parses a date from a ``date``/``datetime``/ISO string/``today``/``tomorrow``."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip().lower()
    today = today or date.today()
    if text == "today":
        return today
    if text == "tomorrow":
        return today + timedelta(days=1)
    try:
        return date.fromisoformat(text)
    except ValueError as exc:
        raise MeetingValidationError(
            f"Invalid date {value!r}; expected YYYY-MM-DD, 'today', or 'tomorrow'."
        ) from exc


def parse_time(value: "str | time") -> time:
    """Parses a time from a ``time`` object or a string (24h or 12h am/pm)."""
    try:
        return parse_clock_time(value)
    except Exception as exc:
        raise MeetingValidationError(str(exc)) from exc


def normalise_participants(value: "None | str | List[str]") -> List[str]:
    """Coerces participants into a clean list of names.

    Accepts a list, a comma-separated string, or ``None``.
    """
    if value is None:
        return []
    if isinstance(value, str):
        items = value.split(",")
    else:
        items = list(value)
    return [str(item).strip() for item in items if str(item).strip()]


@dataclass
class Meeting:
    """A scheduled meeting.

    Fields: ``id``, ``title``, ``location``, ``date``, ``time``,
    ``participants``, ``notes``.
    """

    title: str
    date: date
    time: time
    location: str = ""
    participants: List[str] = field(default_factory=list)
    notes: str = ""
    id: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.title or not str(self.title).strip():
            raise MeetingValidationError("Meeting.title must be a non-empty string.")
        self.date = parse_date(self.date)
        self.time = parse_time(self.time)
        self.participants = normalise_participants(self.participants)

    @property
    def starts_at(self) -> datetime:
        """Combined date + time as a single datetime."""
        return datetime.combine(self.date, self.time)

    def to_row(self) -> Mapping[str, Any]:
        """Serialises into SQLite column values."""
        return {
            "id": self.id,
            "title": self.title,
            "location": self.location,
            "date": self.date.isoformat(),
            "time": self.time.strftime("%H:%M"),
            "participants": json.dumps(self.participants),
            "notes": self.notes,
        }

    @classmethod
    def from_row(cls, row: Mapping[str, Any]) -> "Meeting":
        """Reconstructs a meeting from a SQLite row."""
        raw_participants = row["participants"]
        participants = json.loads(raw_participants) if raw_participants else []
        return cls(
            id=row["id"],
            title=row["title"],
            location=row["location"] or "",
            date=date.fromisoformat(row["date"]),
            time=parse_time(row["time"]),
            participants=participants,
            notes=row["notes"] or "",
        )
