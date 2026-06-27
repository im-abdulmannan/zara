"""Configuration for the intent classifier (environment-driven)."""
from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()

ENV_GEMINI_API_KEY = "GEMINI_API_KEY"
ENV_GOOGLE_API_KEY = "GOOGLE_API_KEY"
ENV_INTENT_MODEL = "INTENT_MODEL"
ENV_INTENT_CONFIDENCE_THRESHOLD = "INTENT_CONFIDENCE_THRESHOLD"
ENV_INTENT_LOG_LEVEL = "INTENT_LOG_LEVEL"

DEFAULT_MODEL = "gemini-2.0-flash"
DEFAULT_CONFIDENCE_THRESHOLD = 0.7
DEFAULT_LOG_LEVEL = "INFO"


def _get_str(name: str, default: str) -> str:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return raw.strip()


def _get_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return float(raw.strip())
    except ValueError:
        return default


@dataclass(frozen=True)
class IntentConfig:
    """Immutable intent-classifier configuration."""

    api_key: str
    model: str = DEFAULT_MODEL
    confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD
    log_level: str = DEFAULT_LOG_LEVEL

    @classmethod
    def from_env(cls) -> "IntentConfig":
        api_key = (
            os.getenv(ENV_GEMINI_API_KEY) or os.getenv(ENV_GOOGLE_API_KEY) or ""
        ).strip()
        return cls(
            api_key=api_key,
            model=_get_str(ENV_INTENT_MODEL, DEFAULT_MODEL),
            confidence_threshold=_get_float(
                ENV_INTENT_CONFIDENCE_THRESHOLD,
                DEFAULT_CONFIDENCE_THRESHOLD,
            ),
            log_level=_get_str(ENV_INTENT_LOG_LEVEL, DEFAULT_LOG_LEVEL),
        )
