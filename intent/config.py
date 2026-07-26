"""Configuration for the intent classifier (environment-driven)."""
from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()

ENV_INTENT_ENABLED = "INTENT_ENABLED"
ENV_INTENT_BACKEND = "INTENT_BACKEND"
ENV_INTENT_BASE_URL = "INTENT_BASE_URL"
ENV_INTENT_API_KEY = "INTENT_API_KEY"
ENV_GEMINI_API_KEY = "GEMINI_API_KEY"
ENV_GOOGLE_API_KEY = "GOOGLE_API_KEY"
ENV_INTENT_MODEL = "INTENT_MODEL"
ENV_INTENT_CONFIDENCE_THRESHOLD = "INTENT_CONFIDENCE_THRESHOLD"
ENV_INTENT_LOG_LEVEL = "INTENT_LOG_LEVEL"

DEFAULT_MODEL = "gemini-2.0-flash"
DEFAULT_CONFIDENCE_THRESHOLD = 0.7
DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_BACKEND = "gemini"


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


def _get_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class IntentConfig:
    """Immutable intent-classifier configuration."""

    enabled: bool = True
    backend: str = DEFAULT_BACKEND  # gemini | openai
    api_key: str = ""
    model: str = DEFAULT_MODEL
    base_url: str = ""
    confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD
    log_level: str = DEFAULT_LOG_LEVEL

    @property
    def uses_gemini(self) -> bool:
        return (self.backend or DEFAULT_BACKEND).lower() == "gemini"

    @classmethod
    def from_env(cls) -> "IntentConfig":
        backend = _get_str(ENV_INTENT_BACKEND, DEFAULT_BACKEND).lower()
        if backend not in {"gemini", "openai"}:
            backend = DEFAULT_BACKEND

        api_key = (
            os.getenv(ENV_INTENT_API_KEY)
            or os.getenv(ENV_GEMINI_API_KEY)
            or os.getenv(ENV_GOOGLE_API_KEY)
            or ""
        ).strip()

        default_model = DEFAULT_MODEL if backend == "gemini" else "openrouter/free"
        return cls(
            enabled=_get_bool(ENV_INTENT_ENABLED, True),
            backend=backend,
            api_key=api_key,
            model=_get_str(ENV_INTENT_MODEL, default_model),
            base_url=_get_str(ENV_INTENT_BASE_URL, ""),
            confidence_threshold=_get_float(
                ENV_INTENT_CONFIDENCE_THRESHOLD,
                DEFAULT_CONFIDENCE_THRESHOLD,
            ),
            log_level=_get_str(ENV_INTENT_LOG_LEVEL, DEFAULT_LOG_LEVEL),
        )
