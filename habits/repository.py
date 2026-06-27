"""Repository: the only place that knows SQL for habits."""
from __future__ import annotations

from typing import List, Optional

from automation.logging_config import get_logger
from habits.config import HabitConfig
from habits.database import connection_scope, init_db
from habits.exceptions import HabitNotFoundError
from habits.models import Habit, HabitStatus

_INSERT_SQL = """
INSERT INTO habits (id, title, frequency, time, status, streak, created_at)
VALUES (:id, :title, :frequency, :time, :status, :streak, :created_at);
"""

_UPDATE_SQL = """
UPDATE habits
   SET title = :title,
       frequency = :frequency,
       time = :time,
       status = :status,
       streak = :streak
 WHERE id = :id;
"""

_SELECT_BY_ID_SQL = "SELECT * FROM habits WHERE id = :id;"
_SELECT_ALL_SQL = "SELECT * FROM habits ORDER BY time ASC, title ASC;"
_SELECT_BY_STATUS_SQL = (
    "SELECT * FROM habits WHERE status = :status ORDER BY time ASC;"
)
_DELETE_SQL = "DELETE FROM habits WHERE id = :id;"


class HabitRepository:
    """SQLite-backed CRUD store for :class:`Habit` objects."""

    def __init__(self, config: Optional[HabitConfig] = None) -> None:
        self._config = config or HabitConfig.from_env()
        self._logger = get_logger(__name__, self._config.log_level)
        init_db(self._config.db_path)

    def add(self, habit: Habit) -> Habit:
        if not habit.id:
            raise ValueError("Habit.id must be set before persisting.")
        with connection_scope(self._config.db_path) as conn:
            conn.execute(_INSERT_SQL, habit.to_row())
        self._logger.debug("Inserted habit id=%s.", habit.id)
        return habit

    def update(self, habit: Habit) -> Habit:
        with connection_scope(self._config.db_path) as conn:
            cursor = conn.execute(_UPDATE_SQL, habit.to_row())
            if cursor.rowcount == 0:
                raise HabitNotFoundError(f"No habit with id {habit.id!r}.")
        self._logger.debug("Updated habit id=%s.", habit.id)
        return habit

    def delete(self, habit_id: str) -> None:
        with connection_scope(self._config.db_path) as conn:
            cursor = conn.execute(_DELETE_SQL, {"id": habit_id})
            if cursor.rowcount == 0:
                raise HabitNotFoundError(f"No habit with id {habit_id!r}.")
        self._logger.debug("Deleted habit id=%s.", habit_id)

    def get(self, habit_id: str) -> Optional[Habit]:
        with connection_scope(self._config.db_path) as conn:
            row = conn.execute(_SELECT_BY_ID_SQL, {"id": habit_id}).fetchone()
        return Habit.from_row(row) if row else None

    def get_or_raise(self, habit_id: str) -> Habit:
        habit = self.get(habit_id)
        if habit is None:
            raise HabitNotFoundError(f"No habit with id {habit_id!r}.")
        return habit

    def list_all(self, status: Optional[HabitStatus] = None) -> List[Habit]:
        with connection_scope(self._config.db_path) as conn:
            if status is None:
                rows = conn.execute(_SELECT_ALL_SQL).fetchall()
            else:
                rows = conn.execute(
                    _SELECT_BY_STATUS_SQL, {"status": status.value}
                ).fetchall()
        return [Habit.from_row(row) for row in rows]
