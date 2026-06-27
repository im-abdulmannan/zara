"""Environment-driven configuration for the automation engine.

All tunables live here and are loaded from environment variables with explicit,
named defaults -- there are no magic numbers scattered through the engine. The
config object is immutable so it can be shared safely across threads.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

# Environment variable names (single source of truth).
ENV_TIMEZONE = "AUTOMATION_TIMEZONE"
ENV_JOBSTORE_URL = "AUTOMATION_JOBSTORE_URL"
ENV_THREAD_POOL_SIZE = "AUTOMATION_THREAD_POOL_SIZE"
ENV_MAX_INSTANCES = "AUTOMATION_MAX_INSTANCES"
ENV_COALESCE = "AUTOMATION_COALESCE"
ENV_MISFIRE_GRACE_TIME = "AUTOMATION_MISFIRE_GRACE_TIME"
ENV_LOG_LEVEL = "AUTOMATION_LOG_LEVEL"

# Defaults (named constants -- not hardcoded at usage sites).
def _local_timezone_name() -> str:
    """Resolves the system's IANA timezone name (e.g. ``"Asia/Karachi"``).

    A desktop assistant schedules against the user's wall clock, so the local
    zone is the sensible default. Falls back to UTC if detection fails.
    """
    try:
        from tzlocal import get_localzone_name

        return get_localzone_name() or "UTC"
    except Exception:  # noqa: BLE001 -- detection is best-effort
        return "UTC"


DEFAULT_TIMEZONE = _local_timezone_name()
# A persistent SQLite store means scheduled reminders survive restarts.
# Set AUTOMATION_JOBSTORE_URL="memory" for an in-memory (non-persistent) store.
DEFAULT_JOBSTORE_URL = "sqlite:///zara_automation.sqlite"
DEFAULT_THREAD_POOL_SIZE = 10
DEFAULT_MAX_INSTANCES = 1
DEFAULT_COALESCE = True
DEFAULT_MISFIRE_GRACE_TIME = 60
DEFAULT_LOG_LEVEL = "INFO"

# Sentinel value selecting the in-memory job store.
MEMORY_JOBSTORE = "memory"

_TRUE_VALUES = {"1", "true", "yes", "on", "y"}
_FALSE_VALUES = {"0", "false", "no", "off", "n"}


def _get_int(name: str, default: int) -> int:
    """Reads a positive integer env var, falling back to ``default``."""
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer, got {raw!r}.") from exc
    if value <= 0:
        raise ValueError(f"{name} must be positive, got {value}.")
    return value


def _get_bool(name: str, default: bool) -> bool:
    """Reads a boolean env var accepting common truthy/falsey spellings."""
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    normalised = raw.strip().lower()
    if normalised in _TRUE_VALUES:
        return True
    if normalised in _FALSE_VALUES:
        return False
    raise ValueError(f"{name} must be a boolean, got {raw!r}.")


def _get_str(name: str, default: str) -> str:
    """Reads a non-empty string env var, falling back to ``default``."""
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return raw.strip()


@dataclass(frozen=True)
class AutomationConfig:
    """Immutable configuration for :class:`~automation.engine.AutomationEngine`.

    Attributes:
        timezone: IANA timezone name used for cron/date triggers.
        jobstore_url: SQLAlchemy URL for the persistent job store, or
            ``"memory"`` to use a non-persistent in-memory store.
        thread_pool_size: Worker threads available to run reminder callbacks.
        max_instances: Max concurrent executions of a single job.
        coalesce: Collapse multiple missed runs into a single one on catch-up.
        misfire_grace_time: Seconds a misfired job may still run late.
        log_level: Logging level name for the package logger.
    """

    timezone: str = DEFAULT_TIMEZONE
    jobstore_url: str = DEFAULT_JOBSTORE_URL
    thread_pool_size: int = DEFAULT_THREAD_POOL_SIZE
    max_instances: int = DEFAULT_MAX_INSTANCES
    coalesce: bool = DEFAULT_COALESCE
    misfire_grace_time: int = DEFAULT_MISFIRE_GRACE_TIME
    log_level: str = DEFAULT_LOG_LEVEL

    @property
    def use_memory_store(self) -> bool:
        """True when the in-memory (non-persistent) job store is selected."""
        return self.jobstore_url.strip().lower() == MEMORY_JOBSTORE

    @classmethod
    def from_env(cls) -> "AutomationConfig":
        """Builds a configuration object from environment variables."""
        return cls(
            timezone=_get_str(ENV_TIMEZONE, DEFAULT_TIMEZONE),
            jobstore_url=_get_str(ENV_JOBSTORE_URL, DEFAULT_JOBSTORE_URL),
            thread_pool_size=_get_int(ENV_THREAD_POOL_SIZE, DEFAULT_THREAD_POOL_SIZE),
            max_instances=_get_int(ENV_MAX_INSTANCES, DEFAULT_MAX_INSTANCES),
            coalesce=_get_bool(ENV_COALESCE, DEFAULT_COALESCE),
            misfire_grace_time=_get_int(
                ENV_MISFIRE_GRACE_TIME, DEFAULT_MISFIRE_GRACE_TIME
            ),
            log_level=_get_str(ENV_LOG_LEVEL, DEFAULT_LOG_LEVEL),
        )
