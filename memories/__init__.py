"""Zara permanent Memory System (SQLite).

Stores durable facts about the user as ``(category, key, value)`` records with
timestamps, using the Repository + Service pattern.

Public API:
    Memory             -- domain model
    MemoryRepository   -- persistence (CRUD + search)
    MemoryService      -- remember / forget / update / search / list
    MemoryConfig       -- env-driven configuration
"""
from memories.config import MemoryConfig
from memories.models import Memory
from memories.repository import MemoryRepository
from memories.service import (
    MemoryService,
    forget,
    list_memories,
    remember,
    search_memory,
    update_memory,
)
from memories.exceptions import (
    MemoryError,
    MemoryNotFoundError,
    MemoryValidationError,
)

__all__ = [
    "MemoryConfig",
    "Memory",
    "MemoryRepository",
    "MemoryService",
    "remember",
    "forget",
    "update_memory",
    "search_memory",
    "list_memories",
    "MemoryError",
    "MemoryNotFoundError",
    "MemoryValidationError",
]
