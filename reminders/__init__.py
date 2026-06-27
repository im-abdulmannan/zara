"""Zara Reminder Service.

A domain layer over APScheduler via :mod:`automation` and
:class:`ReminderScheduler`.

Layering (high level depends on low level, never the reverse)::

    service.py        ReminderService   -- orchestration / use cases
        |                 |        \\
        v                 v         v
    repository.py   scheduler.py   notifications
        |                 |
        v                 v
    database.py       automation.AutomationEngine (APScheduler)
        ^
        |
    models.py         Reminder, RepeatType, ReminderStatus

APScheduler lifecycle (via :class:`ReminderScheduler`):
    create reminder  -> schedule()   -> add APScheduler job
    update reminder  -> reschedule() -> reschedule_job + modify_job
    delete reminder  -> remove()     -> remove_job

Public API:
    Reminder, RepeatType, ReminderStatus  -- domain model
    ReminderRepository                     -- persistence (CRUD)
    ReminderScheduler                      -- APScheduler bridge
    ReminderService                        -- use-case facade
    NotificationMessage, NotificationQueue -- delivery decoupling
"""
from reminders.config import ReminderConfig
from reminders.models import Reminder, RepeatType, ReminderStatus
from reminders.repository import ReminderRepository
from reminders.scheduler import ReminderScheduler
from reminders.notifications import NotificationMessage, NotificationQueue
from reminders.service import ReminderService
from reminders.exceptions import (
    ReminderError,
    ReminderNotFoundError,
    ReminderValidationError,
)

__all__ = [
    "ReminderConfig",
    "Reminder",
    "RepeatType",
    "ReminderStatus",
    "ReminderRepository",
    "ReminderScheduler",
    "NotificationMessage",
    "NotificationQueue",
    "ReminderService",
    "ReminderError",
    "ReminderNotFoundError",
    "ReminderValidationError",
]
