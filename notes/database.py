"""SQLite connection management and schema for notes."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from typing import Iterator

from notes.logging_config import get_logger

_logger = get_logger(__name__)

CREATE_NOTES_TABLE = """
CREATE TABLE IF NOT EXISTS notes (
    id         TEXT PRIMARY KEY,
    title      TEXT NOT NULL,
    content    TEXT NOT NULL,
    tags       TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""

CREATE_TITLE_INDEX = "CREATE INDEX IF NOT EXISTS idx_notes_title ON notes(title);"
CREATE_UPDATED_INDEX = (
    "CREATE INDEX IF NOT EXISTS idx_notes_updated_at ON notes(updated_at);"
)


def get_connection(db_path: str) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode = WAL;")
    connection.execute("PRAGMA foreign_keys = ON;")
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
        connection.execute(CREATE_NOTES_TABLE)
        connection.execute(CREATE_TITLE_INDEX)
        connection.execute(CREATE_UPDATED_INDEX)
    _logger.info("Notes database initialised at %s.", db_path)
