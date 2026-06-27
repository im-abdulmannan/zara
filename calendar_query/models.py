"""Domain models for calendar queries."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Any, List, Mapping, Optional

from meetings.models import Meeting
from reminders.models import Reminder


class QueryType(str, Enum):
    """Supported calendar question types."""

    TODAY = "today"
    TOMORROW = "tomorrow"
    MEETINGS_THIS_WEEK = "meetings_this_week"
    NEXT_MEETING = "next_meeting"
    ALL_REMINDERS = "all_reminders"
    OVERDUE_REMINDERS = "overdue_reminders"
    UNKNOWN = "unknown"

    @classmethod
    def from_value(cls, value: "str | QueryType") -> "QueryType":
        if isinstance(value, cls):
            return value
        normalised = str(value).strip().lower()
        for member in cls:
            if member.value == normalised:
                return member
        return cls.UNKNOWN


@dataclass(frozen=True)
class CalendarQuery:
    """A classified natural-language calendar question."""

    query_type: QueryType
    question: str
    confidence: float = 1.0


@dataclass(frozen=True)
class CalendarQueryResult:
    """Structured answer from the calendar query engine."""

    query: CalendarQuery
    meetings: List[Meeting] = field(default_factory=list)
    reminders: List[Reminder] = field(default_factory=list)
    answer: str = ""
    reference: Optional[datetime] = None

    @property
    def has_items(self) -> bool:
        return bool(self.meetings or self.reminders)

    def to_dict(self) -> dict[str, Any]:
        return {
            "query_type": self.query.query_type.value,
            "question": self.query.question,
            "answer": self.answer,
            "meetings": [
                {
                    "id": meeting.id,
                    "title": meeting.title,
                    "starts_at": meeting.starts_at.isoformat(sep=" "),
                    "location": meeting.location,
                }
                for meeting in self.meetings
            ],
            "reminders": [
                {
                    "id": reminder.id,
                    "title": reminder.title,
                    "remind_at": reminder.remind_at.isoformat(sep=" "),
                    "repeat_type": reminder.repeat_type.value,
                    "status": reminder.status.value,
                }
                for reminder in self.reminders
            ],
        }


@dataclass(frozen=True)
class DaySchedule:
    """Meetings and reminders occurring on a specific day."""

    day: date
    meetings: List[Meeting] = field(default_factory=list)
    reminders: List[Reminder] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not self.meetings and not self.reminders
