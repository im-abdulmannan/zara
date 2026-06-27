"""SQLite connection management and schema for meetings."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from typing import Iterator

from meetings.logging_config import get_logger

_logger = get_logger(__name__)

CREATE_MEETINGS_TABLE = """
CREATE TABLE IF NOT EXISTS meetings (
    id           TEXT PRIMARY KEY,
    title        TEXT NOT NULL,
    location     TEXT NOT NULL DEFAULT '',
    date         TEXT NOT NULL,
    time         TEXT NOT NULL,
    participants TEXT NOT NULL DEFAULT '[]',
    notes        TEXT NOT NULL DEFAULT ''
);
"""

CREATE_DATE_INDEX = (
    "CREATE INDEX IF NOT EXISTS idx_meetings_date ON meetings(date, time);"
)


def get_connection(db_path: str) -> sqlite3.Connection:
    """Opens a configured SQLite connection (row access by name, WAL mode)."""
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode = WAL;")
    return connection


@contextmanager
def connection_scope(db_path: str) -> Iterator[sqlite3.Connection]:
    """Yields a connection that commits on success, rolls back on error, closes."""
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
    """Creates the meetings table and index if they do not exist."""
    with connection_scope(db_path) as connection:
        connection.execute(CREATE_MEETINGS_TABLE)
        connection.execute(CREATE_DATE_INDEX)
    _logger.info("Meeting database initialised at %s.", db_path)
