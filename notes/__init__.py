"""Zara Notes module.

Stores notes in SQLite with structured tags and created/updated timestamps.

Public API:
    Note             -- domain model
    NoteRepository   -- persistence (CRUD + search)
    NoteService      -- create/update/delete/search/list
    NotesConfig      -- env-driven configuration
"""
from notes.config import NotesConfig
from notes.exceptions import NoteError, NoteNotFoundError, NoteValidationError
from notes.models import Note
from notes.repository import NoteRepository
from notes.service import (
    NoteService,
    create_note,
    delete_note,
    list_notes,
    search_note,
    update_note,
)

__all__ = [
    "NotesConfig",
    "Note",
    "NoteRepository",
    "NoteService",
    "create_note",
    "update_note",
    "delete_note",
    "search_note",
    "list_notes",
    "NoteError",
    "NoteNotFoundError",
    "NoteValidationError",
]
