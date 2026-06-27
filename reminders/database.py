"""SQLite connection management and schema initialisation.

A new connection is opened per operation (see :func:`get_connection`). This is
deliberate: reminder callbacks run on APScheduler worker threads, and sqlite3
connections are not safe to share across threads. Per-operation connections are
simple and thread-safe; WAL mode keeps concurrent readers/writers smooth.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from typing import Iterator

from automation.logging_config import get_logger

_logger = get_logger(__name__)

CREATE_REMINDERS_TABLE = """
CREATE TABLE IF NOT EXISTS reminders (
    id          TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    datetime    TEXT NOT NULL,
    repeat_type TEXT NOT NULL,
    status      TEXT NOT NULL,
    created_at  TEXT NOT NULL
);
"""

# Speeds up the common "list active reminders" query.
CREATE_STATUS_INDEX = (
    "CREATE INDEX IF NOT EXISTS idx_reminders_status ON reminders(status);"
)


def get_connection(db_path: str) -> sqlite3.Connection:
    """Opens a configured SQLite connection.

    Row factory is :class:`sqlite3.Row` so columns are accessible by name.
    """
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode = WAL;")
    connection.execute("PRAGMA foreign_keys = ON;")
    return connection


@contextmanager
def connection_scope(db_path: str) -> Iterator[sqlite3.Connection]:
    """Context manager yielding a connection that commits/rolls back and closes.

    Commits on clean exit, rolls back on exception, and always closes.
    """
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
    """Creates the reminders table and indexes if they do not yet exist."""
    with connection_scope(db_path) as connection:
        connection.execute(CREATE_REMINDERS_TABLE)
        connection.execute(CREATE_STATUS_INDEX)
    _logger.info("Reminder database initialised at %s.", db_path)
