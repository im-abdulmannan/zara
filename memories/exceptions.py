"""Exception hierarchy for the memory system."""
from __future__ import annotations


class MemoryError(Exception):
    """Base class for all memory system errors."""


class MemoryNotFoundError(MemoryError):
    """Raised when a memory id/key does not exist."""


class MemoryValidationError(MemoryError):
    """Raised when memory input data is invalid."""
