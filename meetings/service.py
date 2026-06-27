"""Meeting service: use-case layer over the repository."""
from __future__ import annotations

import uuid
from datetime import date, datetime, time, timedelta
from typing import List, Optional

from meetings.config import MeetingConfig
from meetings.logging_config import get_logger
from meetings.models import Meeting
from meetings.repository import MeetingRepository


class MeetingService:
    """High-level API for creating, querying, and managing meetings."""

    def __init__(
        self,
        repository: Optional[MeetingRepository] = None,
        config: Optional[MeetingConfig] = None,
    ) -> None:
        self._config = config or MeetingConfig.from_env()
        self._logger = get_logger(__name__, self._config.log_level)
        self._repo = repository or MeetingRepository(self._config)

    # -- CRUD --------------------------------------------------------------
    def create_meeting(
        self,
        title: str,
        date: "str | date | datetime",
        time: "str | time",
        location: str = "",
        participants: "None | str | List[str]" = None,
        notes: str = "",
    ) -> Meeting:
        """Creates and persists a meeting. ``date``/``time`` accept strings."""
        meeting = Meeting(
            id=uuid.uuid4().hex,
            title=title,
            date=date,
            time=time,
            location=location,
            participants=participants,
            notes=notes,
        )
        self._repo.add(meeting)
        self._logger.info(
            "Created meeting id=%s title=%r at %s.",
            meeting.id,
            meeting.title,
            meeting.starts_at.isoformat(),
        )
        return meeting

    def delete_meeting(self, meeting_id: str) -> None:
        """Deletes a meeting by id (raises if missing)."""
        self._repo.delete(meeting_id)
        self._logger.info("Deleted meeting id=%s.", meeting_id)

    def update_meeting(
        self,
        meeting_id: str,
        *,
        title: Optional[str] = None,
        date: "Optional[str | date | datetime]" = None,
        time: "Optional[str | time]" = None,
        location: Optional[str] = None,
        participants: "None | str | List[str]" = None,
        notes: Optional[str] = None,
    ) -> Meeting:
        """Updates the provided fields of a meeting and persists it."""
        meeting = self._repo.get_or_raise(meeting_id)
        if title is not None:
            meeting.title = title
        if date is not None:
            meeting.date = date
        if time is not None:
            meeting.time = time
        if location is not None:
            meeting.location = location
        if participants is not None:
            meeting.participants = participants
        if notes is not None:
            meeting.notes = notes
        # Re-run validation / coercion via the model invariants.
        meeting.__post_init__()
        self._repo.update(meeting)
        self._logger.info("Updated meeting id=%s.", meeting_id)
        return meeting

    def get_meeting(self, meeting_id: str) -> Meeting:
        """Returns a meeting or raises :class:`MeetingNotFoundError`."""
        return self._repo.get_or_raise(meeting_id)

    # -- queries -----------------------------------------------------------
    def get_meetings_on(self, day: date) -> List[Meeting]:
        """Meetings scheduled for a specific calendar day, ordered by time."""
        return self._repo.by_date(day)

    def get_today_meetings(self) -> List[Meeting]:
        """Meetings scheduled for today, ordered by time."""
        return self.get_meetings_on(date.today())

    def get_tomorrow_meetings(self) -> List[Meeting]:
        """Meetings scheduled for tomorrow, ordered by time."""
        return self.get_meetings_on(date.today() + timedelta(days=1))

    def get_upcoming_meetings(self, limit: Optional[int] = None) -> List[Meeting]:
        """Future meetings from now onward, ordered soonest-first."""
        now = datetime.now()
        meetings = self._repo.upcoming(today=now.date(), now=now.time())
        return meetings[:limit] if limit else meetings

    def get_week_meetings(self) -> List[Meeting]:
        """Meetings from today through the next 7 days."""
        today = date.today()
        return self._repo.between(today, today + timedelta(days=7))

    def find_meeting(self, query: str) -> List[Meeting]:
        """Finds meetings matching ``query`` in title/location/notes/participants."""
        if not query or not query.strip():
            return []
        return self._repo.search(query.strip())
