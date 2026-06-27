"""Configuration for the calendar query engine."""
from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()

ENV_LOG_LEVEL = "CALENDAR_LOG_LEVEL"

DEFAULT_LOG_LEVEL = "INFO"


def _get_str(name: str, default: str) -> str:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return raw.strip()


@dataclass(frozen=True)
class CalendarConfig:
    """Immutable calendar-engine configuration."""

    log_level: str = DEFAULT_LOG_LEVEL

    @classmethod
    def from_env(cls) -> "CalendarConfig":
        return cls(log_level=_get_str(ENV_LOG_LEVEL, DEFAULT_LOG_LEVEL))
