"""Calendar query engine: answers natural-language schedule questions."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import List, Optional

from calendar_query.config import CalendarConfig
from calendar_query.exceptions import CalendarQueryParseError
from calendar_query.formatter import format_result
from calendar_query.logging_config import get_logger
from calendar_query.models import CalendarQuery, CalendarQueryResult, DaySchedule, QueryType
from calendar_query.parser import parse_calendar_question
from calendar_query.reminders import (
    filter_all_listable_reminders,
    filter_overdue_reminders,
    filter_reminders_for_day,
    reminder_display_time,
)
from meetings.models import Meeting
from meetings.service import MeetingService
from reminders.models import Reminder
from reminders.service import ReminderService


class CalendarQueryEngine:
    """Executes natural-language calendar questions against meetings and reminders."""

    def __init__(
        self,
        meeting_service: MeetingService,
        reminder_service: ReminderService,
        config: Optional[CalendarConfig] = None,
    ) -> None:
        self._meetings = meeting_service
        self._reminders = reminder_service
        self._config = config or CalendarConfig.from_env()
        self._logger = get_logger(__name__, self._config.log_level)

    @property
    def config(self) -> CalendarConfig:
        return self._config

    def parse(self, question: str) -> CalendarQuery:
        """Classify *question* into a supported query type."""
        return parse_calendar_question(question)

    def query(
        self,
        question: str,
        *,
        reference: datetime | None = None,
    ) -> CalendarQueryResult:
        """Parse and execute a natural-language calendar question."""
        parsed = self.parse(question)
        if parsed.query_type is QueryType.UNKNOWN:
            raise CalendarQueryParseError(
                f"Unsupported calendar question: {question!r}"
            )
        return self.execute(parsed, reference=reference)

    def execute(
        self,
        query: CalendarQuery,
        *,
        reference: datetime | None = None,
    ) -> CalendarQueryResult:
        """Run a classified calendar query."""
        now = reference or datetime.now()
        query_type = query.query_type

        if query_type is QueryType.TODAY:
            return self._result_for_day(query, now.date(), reference=now)
        if query_type is QueryType.TOMORROW:
            return self._result_for_day(
                query,
                now.date() + timedelta(days=1),
                reference=now,
            )
        if query_type is QueryType.MEETINGS_THIS_WEEK:
            meetings = self._meetings.get_week_meetings()
            result = CalendarQueryResult(
                query=query,
                meetings=meetings,
                reference=now,
            )
            return self._finalize(result)
        if query_type is QueryType.NEXT_MEETING:
            upcoming = self._meetings.get_upcoming_meetings(limit=1)
            result = CalendarQueryResult(
                query=query,
                meetings=upcoming,
                reference=now,
            )
            return self._finalize(result)
        if query_type is QueryType.ALL_REMINDERS:
            reminders = filter_all_listable_reminders(
                self._reminders.list_reminders()
            )
            result = CalendarQueryResult(
                query=query,
                reminders=reminders,
                reference=now,
            )
            return self._finalize(result)
        if query_type is QueryType.OVERDUE_REMINDERS:
            reminders = filter_overdue_reminders(
                self._reminders.list_reminders(status=None),
                now=now,
            )
            result = CalendarQueryResult(
                query=query,
                reminders=reminders,
                reference=now,
            )
            return self._finalize(result)

        raise CalendarQueryParseError(
            f"Unsupported calendar query type: {query_type.value}"
        )

    def day_schedule(
        self,
        day: date,
        *,
        reference: datetime | None = None,
    ) -> DaySchedule:
        """Return meetings and reminders for a specific day."""
        now = reference or datetime.now()
        meetings = self._meetings_for_day(day)
        reminders = filter_reminders_for_day(
            self._reminders.list_reminders(),
            day,
        )
        if day == now.date():
            meetings = [m for m in meetings if m.starts_at >= now]
            reminders = [
                r
                for r in reminders
                if reminder_display_time(r, day) >= now
            ]
        return DaySchedule(day=day, meetings=meetings, reminders=reminders)

    def _meetings_for_day(self, day: date) -> List[Meeting]:
        return self._meetings.get_meetings_on(day)

    def _result_for_day(
        self,
        query: CalendarQuery,
        day: date,
        *,
        reference: datetime,
    ) -> CalendarQueryResult:
        schedule = self.day_schedule(day, reference=reference)
        result = CalendarQueryResult(
            query=query,
            meetings=schedule.meetings,
            reminders=schedule.reminders,
            reference=reference,
        )
        return self._finalize(result)

    def _finalize(self, result: CalendarQueryResult) -> CalendarQueryResult:
        answer = format_result(result)
        final = CalendarQueryResult(
            query=result.query,
            meetings=result.meetings,
            reminders=result.reminders,
            answer=answer,
            reference=result.reference,
        )
        self._logger.info(
            "Calendar query type=%s meetings=%d reminders=%d",
            final.query.query_type.value,
            len(final.meetings),
            len(final.reminders),
        )
        return final


_default_engine: CalendarQueryEngine | None = None


def get_engine(
    meeting_service: MeetingService,
    reminder_service: ReminderService,
) -> CalendarQueryEngine:
    """Return a calendar engine bound to the provided services."""
    return CalendarQueryEngine(
        meeting_service=meeting_service,
        reminder_service=reminder_service,
    )


def query_calendar(
    question: str,
    *,
    meeting_service: MeetingService,
    reminder_service: ReminderService,
    reference: datetime | None = None,
) -> CalendarQueryResult:
    """Parse and execute *question* using freshly constructed services."""
    engine = get_engine(meeting_service, reminder_service)
    return engine.query(question, reference=reference)
