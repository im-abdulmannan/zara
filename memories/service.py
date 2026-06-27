"""Memory service: remember / forget / update / search / list."""
from __future__ import annotations

import uuid
from functools import lru_cache
from typing import List, Optional

from memories.config import DEFAULT_CATEGORY, MemoryConfig
from memories.exceptions import MemoryNotFoundError
from memories.logging_config import get_logger
from memories.models import Memory
from memories.repository import MemoryRepository


class MemoryService:
    """High-level API for storing and recalling durable facts."""

    def __init__(
        self,
        repository: Optional[MemoryRepository] = None,
        config: Optional[MemoryConfig] = None,
    ) -> None:
        self._config = config or MemoryConfig.from_env()
        self._logger = get_logger(__name__, self._config.log_level)
        self._repo = repository or MemoryRepository(self._config)

    def remember(
        self,
        key: str,
        value: str,
        category: str = DEFAULT_CATEGORY,
    ) -> Memory:
        """Stores (or overwrites) a fact, e.g. ``remember('favorite_editor', 'VS Code')``."""
        memory = Memory(
            id=uuid.uuid4().hex,
            key=key,
            value=value,
            category=category,
        )
        stored = self._repo.upsert(memory)
        self._logger.info(
            "Remembered [%s] %r = %r.", stored.category, stored.key, stored.value
        )
        return stored

    def forget(self, key: str, category: Optional[str] = None) -> bool:
        """Deletes the fact(s) matching ``key`` (optionally within a category).

        Returns True if anything was deleted.
        """
        deleted = self._repo.delete_by_key(key, category)
        self._logger.info("Forgot %d memory/memories for key=%r.", deleted, key)
        return deleted > 0

    def update_memory(
        self,
        key: str,
        value: str,
        category: Optional[str] = None,
    ) -> Memory:
        """Updates the value of an existing fact (raises if not found)."""
        matches = self._repo.get_by_key(key, category)
        if not matches:
            raise MemoryNotFoundError(f"No memory found for key {key!r}.")
        target = matches[0]
        self._repo.update_value(target.id, value)
        updated = self._repo.get(target.id)
        self._logger.info("Updated memory %r -> %r.", key, value)
        return updated if updated is not None else target

    def search_memory(self, query: str) -> List[Memory]:
        """Finds facts whose key/value/category matches ``query``."""
        if not query or not query.strip():
            return []
        return self._repo.search(query.strip())

    def list_memories(self, category: Optional[str] = None) -> List[Memory]:
        """Lists all facts, optionally filtered by category."""
        return self._repo.list_all(category=category)

    def recall(self, key: str, category: Optional[str] = None) -> Optional[str]:
        """Convenience: returns the value for ``key`` or ``None``."""
        matches = self._repo.get_by_key(key, category)
        return matches[0].value if matches else None


@lru_cache(maxsize=1)
def _default_service() -> MemoryService:
    return MemoryService()


def remember(
    key: str,
    value: str,
    category: str = DEFAULT_CATEGORY,
) -> Memory:
    """Store or replace a durable fact in SQLite."""
    return _default_service().remember(key=key, value=value, category=category)


def forget(key: str, category: Optional[str] = None) -> bool:
    """Delete one or more durable facts by key and optional category."""
    return _default_service().forget(key=key, category=category)


def update_memory(
    key: str,
    value: str,
    category: Optional[str] = None,
) -> Memory:
    """Update an existing durable fact."""
    return _default_service().update_memory(key=key, value=value, category=category)


def search_memory(query: str) -> List[Memory]:
    """Search durable facts by category, key, or value."""
    return _default_service().search_memory(query=query)


def list_memories(category: Optional[str] = None) -> List[Memory]:
    """List durable facts, optionally filtered by category."""
    return _default_service().list_memories(category=category)
