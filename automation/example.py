"""Runnable example + reference integration for the automation engine.

Run directly to see reminders fire without touching the rest of Zara:

    python -m automation.example

In the real assistant, register a handler that speaks the reminder (see
``speaking_handler`` below) and keep a single shared ``AutomationEngine``
instance alive for the lifetime of the process.
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta
from typing import Any, Mapping

from automation import (
    AutomationConfig,
    AutomationEngine,
    JobSpec,
    ReminderType,
    register_handler,
)


def console_handler(
    reminder_id: str,
    name: str,
    message: str,
    metadata: Mapping[str, Any],
) -> None:
    """Example handler: prints the reminder. Swap for TTS in production."""
    print(f"\n[REMINDER] {name}: {message} (id={reminder_id})\n")


def speaking_handler(
    reminder_id: str,
    name: str,
    message: str,
    metadata: Mapping[str, Any],
) -> None:
    """Production handler that speaks the reminder via Zara's TTS.

    Imported lazily so the automation package has no hard dependency on the
    voice subsystem.
    """
    from voice.tts import speak  # local import to avoid coupling at module load

    speak(message)


def main() -> None:
    # Use a non-persistent store for the demo so it starts clean each run.
    engine = AutomationEngine(config=AutomationConfig(jobstore_url="memory"))
    register_handler(console_handler)
    engine.start()

    # One-time reminder, 3 seconds from now.
    engine.create_job(
        JobSpec(
            name="standup",
            message="Time for the team standup.",
            reminder_type=ReminderType.ONE_TIME,
            schedule={"run_date": datetime.now() + timedelta(seconds=3)},
        )
    )

    # Interval reminder, every 5 seconds.
    interval_job = engine.create_job(
        JobSpec(
            name="hydrate",
            message="Drink some water.",
            reminder_type=ReminderType.INTERVAL,
            schedule={"seconds": 5},
        )
    )

    print("Scheduled jobs:")
    for info in engine.list_jobs():
        print("  ", info.to_dict())

    try:
        time.sleep(12)
    finally:
        engine.pause_job(interval_job.job_id)
        engine.shutdown()


if __name__ == "__main__":
    main()
