"""iCalendar (.ics) export and import utility for Zara meetings."""
from __future__ import annotations

from datetime import datetime, timedelta
import os
from typing import List, Sequence

from meetings.models import Meeting
from meetings.service import MeetingService


def export_meetings_to_ics(meetings: Sequence[Meeting], filepath: str) -> str:
    """Export meeting objects into a standard .ics iCalendar file."""
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Zara AI Assistant//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
    ]

    for meeting in meetings:
        dt_start = meeting.starts_at.strftime("%Y%m%dT%H%M%SZ")
        dt_end = (meeting.starts_at + timedelta(hours=1)).strftime("%Y%m%dT%H%M%SZ")
        summary = (meeting.title or "Meeting").replace("\n", " ").replace(",", "\\,")

        lines.extend(
            [
                "BEGIN:VEVENT",
                f"UID:zara-meeting-{meeting.id}@local",
                f"DTSTAMP:{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}",
                f"DTSTART:{dt_start}",
                f"DTEND:{dt_end}",
                f"SUMMARY:{summary}",
                "DESCRIPTION:Scheduled via Zara Voice AI Assistant",
                "STATUS:CONFIRMED",
                "END:VEVENT",
            ]
        )

    lines.append("END:VCALENDAR")
    ics_data = "\r\n".join(lines)

    os.makedirs(os.path.dirname(os.path.abspath(filepath)) or ".", exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(ics_data)

    return os.path.abspath(filepath)


def import_meetings_from_ics(filepath: str, meeting_service: MeetingService) -> int:
    """Import events from a .ics file into Zara's local Meeting repository."""
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"iCalendar file not found: {filepath}")

    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    imported_count = 0
    in_event = False
    title = "Imported Meeting"
    start_dt: datetime | None = None

    for line in content.splitlines():
        line = line.strip()
        if line == "BEGIN:VEVENT":
            in_event = True
            title = "Imported Meeting"
            start_dt = None
        elif line == "END:VEVENT":
            if in_event and start_dt is not None:
                meeting_service.create_meeting(
                    title=title,
                    date=start_dt.date(),
                    time=start_dt.strftime("%H:%M"),
                )
                imported_count += 1
            in_event = False
        elif in_event:
            if line.startswith("SUMMARY:"):
                title = line[8:].strip() or "Imported Meeting"
            elif line.startswith("DTSTART"):
                raw_dt = line.split(":", 1)[-1].strip()
                try:
                    clean_dt = raw_dt.replace("Z", "")
                    if "T" in clean_dt:
                        start_dt = datetime.strptime(clean_dt[:15], "%Y%m%dT%H%M%S")
                    else:
                        start_dt = datetime.strptime(clean_dt[:8], "%Y%m%d")
                except ValueError:
                    start_dt = datetime.now().replace(second=0, microsecond=0)

    return imported_count
