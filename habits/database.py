"""SQLite connection management and schema for habits."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from typing import Iterator

from automation.logging_config import get_logger

_logger = get_logger(__name__)

CREATE_HABITS_TABLE = """
CREATE TABLE IF NOT EXISTS habits (
    id         TEXT PRIMARY KEY,
    title      TEXT NOT NULL,
    frequency  TEXT NOT NULL,
    time       TEXT NOT NULL,
    status     TEXT NOT NULL,
    streak     INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
"""

CREATE_STATUS_INDEX = (
    "CREATE INDEX IF NOT EXISTS idx_habits_status ON habits(status);"
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
        connection.execute(CREATE_HABITS_TABLE)
        connection.execute(CREATE_STATUS_INDEX)
    _logger.info("Habit database initialised at %s.", db_path)
