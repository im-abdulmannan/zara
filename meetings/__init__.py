"""Zara Meeting Manager.

A SQLite-backed meeting store using the same Repository + Service layering as
the reminders package::

    service.py     MeetingService     -- use cases (create/update/queries/find)
        |
        v
    repository.py  MeetingRepository  -- CRUD + date queries (the only SQL)
        |
        v
    database.py    SQLite connection + schema
        ^
        |
    models.py      Meeting            -- pure domain model

Public API:
    Meeting                    -- domain model
    MeetingRepository          -- persistence (CRUD + queries)
    MeetingService             -- use-case facade
    MeetingConfig              -- env-driven configuration
"""
from meetings.config import MeetingConfig
from meetings.models import Meeting
from meetings.repository import MeetingRepository
from meetings.service import MeetingService
from meetings.exceptions import (
    MeetingError,
    MeetingNotFoundError,
    MeetingValidationError,
)

__all__ = [
    "MeetingConfig",
    "Meeting",
    "MeetingRepository",
    "MeetingService",
    "MeetingError",
    "MeetingNotFoundError",
    "MeetingValidationError",
]
