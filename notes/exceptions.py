"""Exception hierarchy for the notes module."""
from __future__ import annotations


class NoteError(Exception):
    """Base class for all note errors."""


class NoteNotFoundError(NoteError):
    """Raised when a note id does not exist."""


class NoteValidationError(NoteError):
    """Raised when note input data is invalid."""
