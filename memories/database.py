"""SQLite connection management and schema for the memory system."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from typing import Iterator

from memories.logging_config import get_logger

_logger = get_logger(__name__)

# UNIQUE(category, key) lets remember() upsert a fact instead of duplicating it.
CREATE_MEMORIES_TABLE = """
CREATE TABLE IF NOT EXISTS memories (
    id         TEXT PRIMARY KEY,
    category   TEXT NOT NULL DEFAULT 'general',
    key        TEXT NOT NULL,
    value      TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(category, key)
);
"""

CREATE_KEY_INDEX = (
    "CREATE INDEX IF NOT EXISTS idx_memories_key ON memories(key);"
)


def get_connection(db_path: str) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode = WAL;")
    return connection


@contextmanager
def connection_scope(db_path: str) -> Iterator[sqlite3.Connection]:
    connection = get_connection(db_path)
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def init_db(db_path: str) -> None:
    with connection_scope(db_path) as connection:
        connection.execute(CREATE_MEMORIES_TABLE)
        connection.execute(CREATE_KEY_INDEX)
    _logger.info("Memory database initialised at %s.", db_path)
