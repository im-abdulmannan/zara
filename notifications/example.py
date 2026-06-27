"""Runnable example for the notification worker.

    python -m notifications.example

Enqueues several notifications while the worker is already "speaking" and shows
they are delivered FIFO, one at a time, with no overlap -- even when a
competing speaker (the assistant's own reply) tries to speak concurrently.
"""
from __future__ import annotations

import threading
import time

from notifications import (
    ConsoleSpeaker,
    Notification,
    NotificationWorker,
)


def main() -> None:
    # speak_duration simulates the time TTS spends talking, so overlap (if any)
    # would be observable.
    speaker = ConsoleSpeaker(speak_duration=0.6)
    worker = NotificationWorker(speaker=speaker)
    worker.start()

    # Enqueue several reminders rapidly. They must come out in FIFO order.
    for i in range(1, 5):
        worker.enqueue(
            Notification(title=f"Reminder {i}", message=f"this is notification {i}", source="reminder")
        )
    print(f"Enqueued 4 notifications; pending={worker.pending}")

    # A competing speaker: the assistant tries to speak its own reply using the
    # SAME speaker (shared lock), so it waits its turn instead of cutting in.
    def assistant_reply() -> None:
        time.sleep(0.3)  # interrupt mid-stream
        speaker.speak("Assistant reply that must NOT interrupt a reminder.")

    threading.Thread(target=assistant_reply, daemon=True).start()

    # Let everything drain.
    time.sleep(4)
    print(f"Done. pending={worker.pending}, is_speaking={worker.is_speaking}")
    worker.stop()


if __name__ == "__main__":
    main()
