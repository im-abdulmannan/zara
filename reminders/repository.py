"""Repository pattern: the only place that knows SQL for reminders.

The repository exposes intention-revealing CRUD methods and hides SQLite
details from the service layer. It contains no business rules -- it just
persists and retrieves :class:`Reminder` objects. This separation lets the
storage backend change (Postgres, an ORM, an in-memory fake for tests) without
touching the service.
"""
from __future__ import annotations

from typing import List, Optional

from automation.logging_config import get_logger
from reminders.config import ReminderConfig
from reminders.database import connection_scope, init_db
from reminders.exceptions import ReminderNotFoundError
from reminders.models import Reminder, ReminderStatus

_INSERT_SQL = """
INSERT INTO reminders (id, title, description, datetime, repeat_type, status, created_at)
VALUES (:id, :title, :description, :datetime, :repeat_type, :status, :created_at);
"""

_UPDATE_SQL = """
UPDATE reminders
   SET title = :title,
       description = :description,
       datetime = :datetime,
       repeat_type = :repeat_type,
       status = :status
 WHERE id = :id;
"""

_UPDATE_STATUS_SQL = "UPDATE reminders SET status = :status WHERE id = :id;"
_SELECT_BY_ID_SQL = "SELECT * FROM reminders WHERE id = :id;"
_SELECT_ALL_SQL = "SELECT * FROM reminders ORDER BY datetime ASC;"
_SELECT_BY_STATUS_SQL = (
    "SELECT * FROM reminders WHERE status = :status ORDER BY datetime ASC;"
)
_DELETE_SQL = "DELETE FROM reminders WHERE id = :id;"


class ReminderRepository:
    """SQLite-backed CRUD store for :class:`Reminder` objects."""

    def __init__(self, config: Optional[ReminderConfig] = None) -> None:
        self._config = config or ReminderConfig.from_env()
        self._logger = get_logger(__name__, self._config.log_level)
        init_db(self._config.db_path)

    # -- create ------------------------------------------------------------
    def add(self, reminder: Reminder) -> Reminder:
        """Inserts a new reminder. ``reminder.id`` must already be set."""
        if not reminder.id:
            raise ValueError("Reminder.id must be set before persisting.")
        with connection_scope(self._config.db_path) as connection:
            connection.execute(_INSERT_SQL, reminder.to_row())
        self._logger.debug("Inserted reminder id=%s.", reminder.id)
        return reminder

    # -- read --------------------------------------------------------------
    def get(self, reminder_id: str) -> Optional[Reminder]:
        """Returns the reminder, or ``None`` if it does not exist."""
        with connection_scope(self._config.db_path) as connection:
            row = connection.execute(
                _SELECT_BY_ID_SQL, {"id": reminder_id}
            ).fetchone()
        return Reminder.from_row(row) if row else None

    def get_or_raise(self, reminder_id: str) -> Reminder:
        """Returns the reminder or raises :class:`ReminderNotFoundError`."""
        reminder = self.get(reminder_id)
        if reminder is None:
            raise ReminderNotFoundError(f"No reminder with id {reminder_id!r}.")
        return reminder

    def list(self, status: Optional[ReminderStatus] = None) -> List[Reminder]:
        """Lists all reminders, optionally filtered by status."""
        with connection_scope(self._config.db_path) as connection:
            if status is None:
                rows = connection.execute(_SELECT_ALL_SQL).fetchall()
            else:
                rows = connection.execute(
                    _SELECT_BY_STATUS_SQL, {"status": status.value}
                ).fetchall()
        return [Reminder.from_row(row) for row in rows]

    # -- update ------------------------------------------------------------
    def update(self, reminder: Reminder) -> Reminder:
        """Updates a reminder's mutable fields. Raises if it does not exist."""
        with connection_scope(self._config.db_path) as connection:
            cursor = connection.execute(_UPDATE_SQL, reminder.to_row())
            if cursor.rowcount == 0:
                raise ReminderNotFoundError(f"No reminder with id {reminder.id!r}.")
        self._logger.debug("Updated reminder id=%s.", reminder.id)
        return reminder

    def update_status(self, reminder_id: str, status: ReminderStatus) -> None:
        """Updates only the status column. Raises if the reminder is missing."""
        with connection_scope(self._config.db_path) as connection:
            cursor = connection.execute(
                _UPDATE_STATUS_SQL, {"id": reminder_id, "status": status.value}
            )
            if cursor.rowcount == 0:
                raise ReminderNotFoundError(f"No reminder with id {reminder_id!r}.")
        self._logger.debug("Reminder id=%s status -> %s.", reminder_id, status.value)

    # -- delete ------------------------------------------------------------
    def delete(self, reminder_id: str) -> None:
        """Deletes a reminder. Raises if it does not exist."""
        with connection_scope(self._config.db_path) as connection:
            cursor = connection.execute(_DELETE_SQL, {"id": reminder_id})
            if cursor.rowcount == 0:
                raise ReminderNotFoundError(f"No reminder with id {reminder_id!r}.")
        self._logger.debug("Deleted reminder id=%s.", reminder_id)
