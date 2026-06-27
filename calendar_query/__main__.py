"""CLI for manual calendar query testing.

Usage:
    python -m calendar_query "What do I have today?"
    python -m calendar_query "Show overdue reminders"
"""
from __future__ import annotations

import json
import sys

from dotenv import load_dotenv

load_dotenv()

from calendar_query import CalendarQueryEngine, CalendarQueryParseError
from runtime import get_runtime


def main() -> None:
    if len(sys.argv) < 2:
        print('Usage: python -m calendar_query "What do I have today?"')
        sys.exit(1)

    question = " ".join(sys.argv[1:])
    runtime = get_runtime()
    engine = CalendarQueryEngine(
        meeting_service=runtime.meeting_service,
        reminder_service=runtime.reminder_service,
    )

    try:
        result = engine.query(question)
    except CalendarQueryParseError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    print(json.dumps(result.to_dict(), indent=2))


if __name__ == "__main__":
    main()
