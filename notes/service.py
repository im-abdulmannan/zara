"""Note service: create / update / delete / search / list."""
from __future__ import annotations

import uuid
from functools import lru_cache
from typing import Iterable, List, Optional

from notes.config import NotesConfig
from notes.exceptions import NoteNotFoundError
from notes.logging_config import get_logger
from notes.models import Note
from notes.repository import NoteRepository


class NoteService:
    """High-level API for managing user notes."""

    def __init__(
        self,
        repository: Optional[NoteRepository] = None,
        config: Optional[NotesConfig] = None,
    ) -> None:
        self._config = config or NotesConfig.from_env()
        self._logger = get_logger(__name__, self._config.log_level)
        self._repo = repository or NoteRepository(self._config)

    def create_note(
        self,
        title: str,
        content: str,
        tags: "str | Iterable[str] | None" = None,
    ) -> Note:
        """Creates and persists a note."""
        note = Note(
            id=uuid.uuid4().hex,
            title=title,
            content=content,
            tags=tags,
        )
        stored = self._repo.add(note)
        self._logger.info("Created note id=%s title=%r.", stored.id, stored.title)
        return stored

    def update_note(
        self,
        note_id: str,
        *,
        title: Optional[str] = None,
        content: Optional[str] = None,
        tags: "str | Iterable[str] | None" = None,
    ) -> Note:
        """Updates a note. Omitted fields keep their existing values."""
        note = self._repo.get_or_raise(note_id)
        if title is not None:
            note.title = title
        if content is not None:
            note.content = content
        if tags is not None:
            note.tags = tags
        note.__post_init__()
        updated = self._repo.update(note)
        self._logger.info("Updated note id=%s.", note_id)
        return updated

    def delete_note(self, note_id: str) -> None:
        """Deletes a note by id."""
        self._repo.delete(note_id)
        self._logger.info("Deleted note id=%s.", note_id)

    def search_note(self, query: str) -> List[Note]:
        """Finds notes whose title, content, or tags match ``query``."""
        if not query or not query.strip():
            return []
        return self._repo.search(query.strip())

    def list_notes(self) -> List[Note]:
        """Lists all notes, newest updates first."""
        return self._repo.list_all()

    def get_note(self, note_id: str) -> Note:
        """Returns a note by id or raises :class:`NoteNotFoundError`."""
        return self._repo.get_or_raise(note_id)


@lru_cache(maxsize=1)
def _default_service() -> NoteService:
    return NoteService()


def create_note(
    title: str,
    content: str,
    tags: "str | Iterable[str] | None" = None,
) -> Note:
    """Create and persist a note in SQLite."""
    return _default_service().create_note(title=title, content=content, tags=tags)


def update_note(
    note_id: str,
    *,
    title: Optional[str] = None,
    content: Optional[str] = None,
    tags: "str | Iterable[str] | None" = None,
) -> Note:
    """Update a note by id."""
    return _default_service().update_note(
        note_id=note_id,
        title=title,
        content=content,
        tags=tags,
    )


def delete_note(note_id: str) -> None:
    """Delete a note by id."""
    _default_service().delete_note(note_id)


def search_note(query: str) -> List[Note]:
    """Search notes by title, content, or tags."""
    return _default_service().search_note(query=query)


def list_notes() -> List[Note]:
    """List all notes."""
    return _default_service().list_notes()
