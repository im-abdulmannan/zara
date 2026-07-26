"""External Calendar & Email Integration Package."""
from __future__ import annotations

from calendar_sync.ical_sync import export_meetings_to_ics, import_meetings_from_ics

__all__ = [
    "export_meetings_to_ics",
    "import_meetings_from_ics",
]
