"""Configuration for the natural-language time parser."""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import time

from dotenv import load_dotenv

load_dotenv()

ENV_DEFAULT_HOUR = "TIME_PARSER_DEFAULT_HOUR"
ENV_DEFAULT_MINUTE = "TIME_PARSER_DEFAULT_MINUTE"
ENV_LOG_LEVEL = "TIME_PARSER_LOG_LEVEL"

DEFAULT_HOUR = 9
DEFAULT_MINUTE = 0
DEFAULT_LOG_LEVEL = "INFO"


def _get_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw.strip())
    except ValueError:
        return default


def _get_str(name: str, default: str) -> str:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return raw.strip()


@dataclass(frozen=True)
class TimeParserConfig:
    """Immutable parser configuration."""

    default_time: time = time(DEFAULT_HOUR, DEFAULT_MINUTE)
    log_level: str = DEFAULT_LOG_LEVEL

    @classmethod
    def from_env(cls) -> "TimeParserConfig":
        hour = _get_int(ENV_DEFAULT_HOUR, DEFAULT_HOUR)
        minute = _get_int(ENV_DEFAULT_MINUTE, DEFAULT_MINUTE)
        hour = max(0, min(23, hour))
        minute = max(0, min(59, minute))
        return cls(
            default_time=time(hour, minute),
            log_level=_get_str(ENV_LOG_LEVEL, DEFAULT_LOG_LEVEL),
        )
