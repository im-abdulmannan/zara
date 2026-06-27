"""Repository: the only place that knows SQL for meetings."""
from __future__ import annotations

from datetime import date, time
from typing import List, Optional

from meetings.config import MeetingConfig
from meetings.database import connection_scope, init_db
from meetings.exceptions import MeetingNotFoundError
from meetings.logging_config import get_logger
from meetings.models import Meeting

_INSERT_SQL = """
INSERT INTO meetings (id, title, location, date, time, participants, notes)
VALUES (:id, :title, :location, :date, :time, :participants, :notes);
"""

_UPDATE_SQL = """
UPDATE meetings
   SET title = :title,
       location = :location,
       date = :date,
       time = :time,
       participants = :participants,
       notes = :notes
 WHERE id = :id;
"""

_SELECT_BY_ID_SQL = "SELECT * FROM meetings WHERE id = :id;"
_SELECT_ALL_SQL = "SELECT * FROM meetings ORDER BY date ASC, time ASC;"
_SELECT_BY_DATE_SQL = (
    "SELECT * FROM meetings WHERE date = :date ORDER BY time ASC;"
)
_SELECT_BETWEEN_SQL = (
    "SELECT * FROM meetings WHERE date BETWEEN :start AND :end "
    "ORDER BY date ASC, time ASC;"
)
_SELECT_UPCOMING_SQL = """
SELECT * FROM meetings
 WHERE date > :today OR (date = :today AND time >= :now)
 ORDER BY date ASC, time ASC;
"""
_SEARCH_SQL = """
SELECT * FROM meetings
 WHERE lower(title) LIKE :q
    OR lower(location) LIKE :q
    OR lower(notes) LIKE :q
    OR lower(participants) LIKE :q
 ORDER BY date ASC, time ASC;
"""
_DELETE_SQL = "DELETE FROM meetings WHERE id = :id;"


class MeetingRepository:
    """SQLite-backed CRUD + date-query store for :class:`Meeting` objects."""

    def __init__(self, config: Optional[MeetingConfig] = None) -> None:
        self._config = config or MeetingConfig.from_env()
        self._logger = get_logger(__name__, self._config.log_level)
        init_db(self._config.db_path)

    # -- create / update / delete -----------------------------------------
    def add(self, meeting: Meeting) -> Meeting:
        if not meeting.id:
            raise ValueError("Meeting.id must be set before persisting.")
        with connection_scope(self._config.db_path) as conn:
            conn.execute(_INSERT_SQL, meeting.to_row())
        self._logger.debug("Inserted meeting id=%s.", meeting.id)
        return meeting

    def update(self, meeting: Meeting) -> Meeting:
        with connection_scope(self._config.db_path) as conn:
            cursor = conn.execute(_UPDATE_SQL, meeting.to_row())
            if cursor.rowcount == 0:
                raise MeetingNotFoundError(f"No meeting with id {meeting.id!r}.")
        self._logger.debug("Updated meeting id=%s.", meeting.id)
        return meeting

    def delete(self, meeting_id: str) -> None:
        with connection_scope(self._config.db_path) as conn:
            cursor = conn.execute(_DELETE_SQL, {"id": meeting_id})
            if cursor.rowcount == 0:
                raise MeetingNotFoundError(f"No meeting with id {meeting_id!r}.")
        self._logger.debug("Deleted meeting id=%s.", meeting_id)

    # -- read --------------------------------------------------------------
    def get(self, meeting_id: str) -> Optional[Meeting]:
        with connection_scope(self._config.db_path) as conn:
            row = conn.execute(_SELECT_BY_ID_SQL, {"id": meeting_id}).fetchone()
        return Meeting.from_row(row) if row else None

    def get_or_raise(self, meeting_id: str) -> Meeting:
        meeting = self.get(meeting_id)
        if meeting is None:
            raise MeetingNotFoundError(f"No meeting with id {meeting_id!r}.")
        return meeting

    def list_all(self) -> List[Meeting]:
        with connection_scope(self._config.db_path) as conn:
            rows = conn.execute(_SELECT_ALL_SQL).fetchall()
        return [Meeting.from_row(row) for row in rows]

    def by_date(self, on: date) -> List[Meeting]:
        with connection_scope(self._config.db_path) as conn:
            rows = conn.execute(_SELECT_BY_DATE_SQL, {"date": on.isoformat()}).fetchall()
        return [Meeting.from_row(row) for row in rows]

    def between(self, start: date, end: date) -> List[Meeting]:
        with connection_scope(self._config.db_path) as conn:
            rows = conn.execute(
                _SELECT_BETWEEN_SQL,
                {"start": start.isoformat(), "end": end.isoformat()},
            ).fetchall()
        return [Meeting.from_row(row) for row in rows]

    def upcoming(self, today: date, now: time) -> List[Meeting]:
        with connection_scope(self._config.db_path) as conn:
            rows = conn.execute(
                _SELECT_UPCOMING_SQL,
                {"today": today.isoformat(), "now": now.strftime("%H:%M")},
            ).fetchall()
        return [Meeting.from_row(row) for row in rows]

    def search(self, query: str) -> List[Meeting]:
        pattern = f"%{query.lower()}%"
        with connection_scope(self._config.db_path) as conn:
            rows = conn.execute(_SEARCH_SQL, {"q": pattern}).fetchall()
        return [Meeting.from_row(row) for row in rows]
