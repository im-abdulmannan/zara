"""Repository: the only place that knows SQL for notes."""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from notes.config import NotesConfig
from notes.database import connection_scope, init_db
from notes.exceptions import NoteNotFoundError
from notes.logging_config import get_logger
from notes.models import Note

_INSERT_SQL = """
INSERT INTO notes (id, title, content, tags, created_at, updated_at)
VALUES (:id, :title, :content, :tags, :created_at, :updated_at);
"""

_UPDATE_SQL = """
UPDATE notes
   SET title = :title,
       content = :content,
       tags = :tags,
       updated_at = :updated_at
 WHERE id = :id;
"""

_SELECT_BY_ID_SQL = "SELECT * FROM notes WHERE id = :id;"
_SELECT_ALL_SQL = "SELECT * FROM notes ORDER BY updated_at DESC, title ASC;"
_SEARCH_SQL = """
SELECT * FROM notes
 WHERE lower(title) LIKE :q
    OR lower(content) LIKE :q
    OR lower(tags) LIKE :q
 ORDER BY updated_at DESC, title ASC;
"""
_DELETE_SQL = "DELETE FROM notes WHERE id = :id;"


class NoteRepository:
    """SQLite-backed CRUD + search store for :class:`Note` objects."""

    def __init__(self, config: Optional[NotesConfig] = None) -> None:
        self._config = config or NotesConfig.from_env()
        self._logger = get_logger(__name__, self._config.log_level)
        init_db(self._config.db_path)

    def add(self, note: Note) -> Note:
        if not note.id:
            raise ValueError("Note.id must be set before persisting.")
        with connection_scope(self._config.db_path) as conn:
            conn.execute(_INSERT_SQL, note.to_row())
        self._logger.debug("Inserted note id=%s title=%r.", note.id, note.title)
        return self.get_or_raise(note.id)

    def update(self, note: Note) -> Note:
        note.updated_at = datetime.now()
        with connection_scope(self._config.db_path) as conn:
            cursor = conn.execute(_UPDATE_SQL, note.to_row())
            if cursor.rowcount == 0:
                raise NoteNotFoundError(f"No note with id {note.id!r}.")
        self._logger.debug("Updated note id=%s.", note.id)
        return self.get_or_raise(note.id)

    def delete(self, note_id: str) -> None:
        with connection_scope(self._config.db_path) as conn:
            cursor = conn.execute(_DELETE_SQL, {"id": note_id})
            if cursor.rowcount == 0:
                raise NoteNotFoundError(f"No note with id {note_id!r}.")
        self._logger.debug("Deleted note id=%s.", note_id)

    def get(self, note_id: str) -> Optional[Note]:
        with connection_scope(self._config.db_path) as conn:
            row = conn.execute(_SELECT_BY_ID_SQL, {"id": note_id}).fetchone()
        return Note.from_row(row) if row else None

    def get_or_raise(self, note_id: str) -> Note:
        note = self.get(note_id)
        if note is None:
            raise NoteNotFoundError(f"No note with id {note_id!r}.")
        return note

    def list_all(self) -> List[Note]:
        with connection_scope(self._config.db_path) as conn:
            rows = conn.execute(_SELECT_ALL_SQL).fetchall()
        return [Note.from_row(row) for row in rows]

    def search(self, query: str) -> List[Note]:
        pattern = f"%{query.strip().lower()}%"
        with connection_scope(self._config.db_path) as conn:
            rows = conn.execute(_SEARCH_SQL, {"q": pattern}).fetchall()
        return [Note.from_row(row) for row in rows]
