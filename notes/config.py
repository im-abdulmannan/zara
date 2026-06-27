"""Configuration for Zara notes (environment-driven)."""
from __future__ import annotations

import os
from dataclasses import dataclass

ENV_DB_PATH = "NOTES_DB_PATH"
ENV_LOG_LEVEL = "NOTES_LOG_LEVEL"

DEFAULT_DB_PATH = "zara_notes.sqlite"
DEFAULT_LOG_LEVEL = "INFO"


def _get_str(name: str, default: str) -> str:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return raw.strip()


@dataclass(frozen=True)
class NotesConfig:
    """Immutable notes configuration."""

    db_path: str = DEFAULT_DB_PATH
    log_level: str = DEFAULT_LOG_LEVEL

    @classmethod
    def from_env(cls) -> "NotesConfig":
        return cls(
            db_path=_get_str(ENV_DB_PATH, DEFAULT_DB_PATH),
            log_level=_get_str(ENV_LOG_LEVEL, DEFAULT_LOG_LEVEL),
        )
