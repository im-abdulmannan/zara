"""Repository: the only place that knows SQL for memories."""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from memories.config import MemoryConfig
from memories.database import connection_scope, init_db
from memories.exceptions import MemoryNotFoundError
from memories.logging_config import get_logger
from memories.models import Memory

# Upsert: insert, or on (category,key) conflict overwrite value + updated_at.
_UPSERT_SQL = """
INSERT INTO memories (id, category, key, value, created_at, updated_at)
VALUES (:id, :category, :key, :value, :created_at, :updated_at)
ON CONFLICT(category, key) DO UPDATE SET
    value = excluded.value,
    updated_at = excluded.updated_at;
"""

_UPDATE_VALUE_SQL = (
    "UPDATE memories SET value = :value, updated_at = :updated_at WHERE id = :id;"
)
_SELECT_BY_ID_SQL = "SELECT * FROM memories WHERE id = :id;"
_SELECT_BY_KEY_SQL = (
    "SELECT * FROM memories WHERE key = :key "
    "AND (:category IS NULL OR category = :category) "
    "ORDER BY updated_at DESC;"
)
_SELECT_ALL_SQL = "SELECT * FROM memories ORDER BY category ASC, key ASC;"
_SELECT_BY_CATEGORY_SQL = (
    "SELECT * FROM memories WHERE category = :category ORDER BY key ASC;"
)
_SEARCH_SQL = """
SELECT * FROM memories
 WHERE lower(key) LIKE :q OR lower(value) LIKE :q OR lower(category) LIKE :q
 ORDER BY updated_at DESC;
"""
_DELETE_BY_ID_SQL = "DELETE FROM memories WHERE id = :id;"
_DELETE_BY_KEY_SQL = (
    "DELETE FROM memories WHERE key = :key "
    "AND (:category IS NULL OR category = :category);"
)


class MemoryRepository:
    """SQLite-backed CRUD + search store for :class:`Memory` objects."""

    def __init__(self, config: Optional[MemoryConfig] = None) -> None:
        self._config = config or MemoryConfig.from_env()
        self._logger = get_logger(__name__, self._config.log_level)
        init_db(self._config.db_path)

    def upsert(self, memory: Memory) -> Memory:
        """Inserts or updates a memory keyed by ``(category, key)``."""
        if not memory.id:
            raise ValueError("Memory.id must be set before persisting.")
        with connection_scope(self._config.db_path) as conn:
            conn.execute(_UPSERT_SQL, memory.to_row())
        self._logger.debug("Upserted memory key=%r category=%r.", memory.key, memory.category)
        # Return the canonical stored row (id may differ on conflict).
        stored = self.get_by_key(memory.key, memory.category)
        return stored[0] if stored else memory

    def update_value(self, memory_id: str, value: str) -> None:
        with connection_scope(self._config.db_path) as conn:
            cursor = conn.execute(
                _UPDATE_VALUE_SQL,
                {"id": memory_id, "value": value, "updated_at": datetime.now().isoformat()},
            )
            if cursor.rowcount == 0:
                raise MemoryNotFoundError(f"No memory with id {memory_id!r}.")

    def get(self, memory_id: str) -> Optional[Memory]:
        with connection_scope(self._config.db_path) as conn:
            row = conn.execute(_SELECT_BY_ID_SQL, {"id": memory_id}).fetchone()
        return Memory.from_row(row) if row else None

    def get_by_key(self, key: str, category: Optional[str] = None) -> List[Memory]:
        with connection_scope(self._config.db_path) as conn:
            rows = conn.execute(
                _SELECT_BY_KEY_SQL, {"key": str(key).strip(), "category": category}
            ).fetchall()
        return [Memory.from_row(row) for row in rows]

    def list_all(self, category: Optional[str] = None) -> List[Memory]:
        with connection_scope(self._config.db_path) as conn:
            if category is None:
                rows = conn.execute(_SELECT_ALL_SQL).fetchall()
            else:
                rows = conn.execute(
                    _SELECT_BY_CATEGORY_SQL, {"category": category}
                ).fetchall()
        return [Memory.from_row(row) for row in rows]

    def search(self, query: str) -> List[Memory]:
        pattern = f"%{query.lower()}%"
        with connection_scope(self._config.db_path) as conn:
            rows = conn.execute(_SEARCH_SQL, {"q": pattern}).fetchall()
        return [Memory.from_row(row) for row in rows]

    def delete(self, memory_id: str) -> None:
        with connection_scope(self._config.db_path) as conn:
            cursor = conn.execute(_DELETE_BY_ID_SQL, {"id": memory_id})
            if cursor.rowcount == 0:
                raise MemoryNotFoundError(f"No memory with id {memory_id!r}.")

    def delete_by_key(self, key: str, category: Optional[str] = None) -> int:
        """Deletes memories matching ``key`` (and optional category). Returns count."""
        with connection_scope(self._config.db_path) as conn:
            cursor = conn.execute(
                _DELETE_BY_KEY_SQL, {"key": str(key).strip(), "category": category}
            )
            return cursor.rowcount
