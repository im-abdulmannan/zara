"""Zara Automation Engine.

A modular, background reminder/scheduling engine built on APScheduler.

Public API:
    AutomationEngine     -- lifecycle + job management facade
    AutomationConfig     -- environment-driven configuration
    JobSpec / JobInfo    -- input / output data models
    ReminderType         -- supported reminder kinds
    register_handler     -- register a callable invoked when a reminder fires
"""
from automation.config import AutomationConfig
from automation.enums import ReminderType
from automation.models import JobInfo, JobSpec
from automation.engine import AutomationEngine
from automation.callbacks import (
    register_handler,
    unregister_handler,
    clear_handlers,
)
from automation.exceptions import (
    AutomationError,
    DuplicateJobError,
    InvalidScheduleError,
    JobNotFoundError,
    SchedulerNotRunningError,
    UnsupportedReminderTypeError,
)

__all__ = [
    "AutomationEngine",
    "AutomationConfig",
    "JobSpec",
    "JobInfo",
    "ReminderType",
    "register_handler",
    "unregister_handler",
    "clear_handlers",
    "AutomationError",
    "DuplicateJobError",
    "InvalidScheduleError",
    "JobNotFoundError",
    "SchedulerNotRunningError",
    "UnsupportedReminderTypeError",
]
