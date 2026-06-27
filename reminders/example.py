"""Runnable example + reference wiring for the reminder service.

    python -m reminders.example

Demonstrates the full stack: repository (SQLite) + automation engine +
notification queue + service, plus a consumer thread that drains the queue and
"presents" notifications (here: prints; in Zara: speaks).
"""
from __future__ import annotations

import os
import queue
import tempfile
import threading
import time
from datetime import datetime, timedelta

from automation import AutomationConfig, AutomationEngine
from reminders import (
    NotificationQueue,
    ReminderConfig,
    ReminderRepository,
    ReminderScheduler,
    ReminderService,
    RepeatType,
)


def consume(notifications: NotificationQueue, stop: threading.Event) -> None:
    """Consumer loop: drains notifications and presents them.

    In production this is where Zara would call ``speak(notification.summary())``.
    Kept separate from the firing thread so reminders never block on audio.
    """
    while not stop.is_set():
        try:
            note = notifications.get(timeout=0.5)
        except queue.Empty:
            continue
        print(f"\n[NOTIFY] {note.summary()}  (repeat={note.repeat_type})\n")
        notifications.task_done()


def main() -> None:
    db_path = os.path.join(tempfile.gettempdir(), "zara_reminders_demo.sqlite")
    if os.path.exists(db_path):
        os.remove(db_path)

    # Compose the object graph (dependency injection at the edge).
    engine = AutomationEngine(config=AutomationConfig(jobstore_url="memory"))
    repository = ReminderRepository(ReminderConfig(db_path=db_path))
    notifications = NotificationQueue()
    scheduler = ReminderScheduler(engine)
    service = ReminderService(scheduler, repository, notifications)

    stop = threading.Event()
    consumer = threading.Thread(target=consume, args=(notifications, stop), daemon=True)
    consumer.start()

    service.start()

    # One-time reminder, ~3 seconds from now.
    once = service.create_reminder(
        title="Standup",
        description="Join the daily standup call.",
        remind_at=datetime.now() + timedelta(seconds=3),
        repeat_type=RepeatType.ONCE,
    )

    # A daily reminder (won't fire during the demo; shown for listing/CRUD).
    service.create_reminder(
        title="Take medication",
        description="Evening dose.",
        remind_at=datetime.now().replace(hour=21, minute=0),
        repeat_type=RepeatType.DAILY,
    )

    print("Reminders in DB:")
    for reminder in service.list_reminders():
        print("  ", reminder.id[:8], reminder.title, reminder.status.value)

    time.sleep(5)  # let the one-time reminder fire and be consumed

    print("Status of one-time reminder after firing:",
          service.get_reminder(once.id).status.value)

    stop.set()
    service.shutdown()
    os.remove(db_path) if os.path.exists(db_path) else None


if __name__ == "__main__":
    main()
