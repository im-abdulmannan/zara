"""Configuration for the reminder service.

Keeps the SQLite location (and any future tunables) out of the code and in the
environment, consistent with the automation package's config approach.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

ENV_DB_PATH = "REMINDER_DB_PATH"
ENV_LOG_LEVEL = "REMINDER_LOG_LEVEL"

# Stored alongside the project by default; override via the environment.
DEFAULT_DB_PATH = "zara_reminders.sqlite"
DEFAULT_LOG_LEVEL = "INFO"


def _get_str(name: str, default: str) -> str:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return raw.strip()


@dataclass(frozen=True)
class ReminderConfig:
    """Immutable reminder-service configuration.

    Attributes:
        db_path: Filesystem path to the reminders SQLite database.
        log_level: Logging level name for the package logger.
    """

    db_path: str = DEFAULT_DB_PATH
    log_level: str = DEFAULT_LOG_LEVEL

    @classmethod
    def from_env(cls) -> "ReminderConfig":
        """Builds configuration from environment variables."""
        return cls(
            db_path=_get_str(ENV_DB_PATH, DEFAULT_DB_PATH),
            log_level=_get_str(ENV_LOG_LEVEL, DEFAULT_LOG_LEVEL),
        )
