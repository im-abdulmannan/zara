"""Configuration for the meeting manager (environment-driven)."""
from __future__ import annotations

import os
from dataclasses import dataclass

ENV_DB_PATH = "MEETING_DB_PATH"
ENV_LOG_LEVEL = "MEETING_LOG_LEVEL"

DEFAULT_DB_PATH = "zara_meetings.sqlite"
DEFAULT_LOG_LEVEL = "INFO"


def _get_str(name: str, default: str) -> str:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return raw.strip()


@dataclass(frozen=True)
class MeetingConfig:
    """Immutable meeting-manager configuration."""

    db_path: str = DEFAULT_DB_PATH
    log_level: str = DEFAULT_LOG_LEVEL

    @classmethod
    def from_env(cls) -> "MeetingConfig":
        return cls(
            db_path=_get_str(ENV_DB_PATH, DEFAULT_DB_PATH),
            log_level=_get_str(ENV_LOG_LEVEL, DEFAULT_LOG_LEVEL),
        )
