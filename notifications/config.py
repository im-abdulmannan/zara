"""Configuration for the notification subsystem (environment-driven)."""
from __future__ import annotations

import os
from dataclasses import dataclass

ENV_QUEUE_MAXSIZE = "NOTIFY_QUEUE_MAXSIZE"
ENV_POLL_TIMEOUT = "NOTIFY_POLL_TIMEOUT"
ENV_SHUTDOWN_TIMEOUT = "NOTIFY_SHUTDOWN_TIMEOUT"
ENV_LOG_LEVEL = "NOTIFY_LOG_LEVEL"

# 0 == unbounded queue (reminders should never be dropped).
DEFAULT_QUEUE_MAXSIZE = 0
# How long the worker blocks waiting for an item before re-checking its stop
# flag. Small enough to stop promptly, large enough to avoid a busy loop.
DEFAULT_POLL_TIMEOUT = 0.5
# Max seconds to wait for the worker thread to finish on shutdown.
DEFAULT_SHUTDOWN_TIMEOUT = 5.0
DEFAULT_LOG_LEVEL = "INFO"


def _get_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer, got {raw!r}.") from exc
    if value < 0:
        raise ValueError(f"{name} must be >= 0, got {value}.")
    return value


def _get_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number, got {raw!r}.") from exc
    if value <= 0:
        raise ValueError(f"{name} must be positive, got {value}.")
    return value


def _get_str(name: str, default: str) -> str:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return raw.strip()


@dataclass(frozen=True)
class NotificationConfig:
    """Immutable configuration for the notification worker.

    Attributes:
        queue_maxsize: Max queued notifications (0 == unbounded).
        poll_timeout: Seconds the worker blocks on an empty queue per cycle.
        shutdown_timeout: Seconds to wait for the worker thread to join.
        log_level: Logging level name for the package logger.
    """

    queue_maxsize: int = DEFAULT_QUEUE_MAXSIZE
    poll_timeout: float = DEFAULT_POLL_TIMEOUT
    shutdown_timeout: float = DEFAULT_SHUTDOWN_TIMEOUT
    log_level: str = DEFAULT_LOG_LEVEL

    @classmethod
    def from_env(cls) -> "NotificationConfig":
        return cls(
            queue_maxsize=_get_int(ENV_QUEUE_MAXSIZE, DEFAULT_QUEUE_MAXSIZE),
            poll_timeout=_get_float(ENV_POLL_TIMEOUT, DEFAULT_POLL_TIMEOUT),
            shutdown_timeout=_get_float(ENV_SHUTDOWN_TIMEOUT, DEFAULT_SHUTDOWN_TIMEOUT),
            log_level=_get_str(ENV_LOG_LEVEL, DEFAULT_LOG_LEVEL),
        )
