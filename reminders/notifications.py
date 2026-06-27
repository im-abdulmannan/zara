"""Notification delivery decoupling.

When a reminder fires, the service does NOT speak. It builds a
:class:`NotificationMessage` and pushes it onto a thread-safe
:class:`NotificationQueue`. A consumer elsewhere (the assistant's main loop, a
dedicated worker thread, a desktop-notification bridge, ...) drains the queue
and decides how to present it. This keeps the reminder domain free of any
presentation concern and lets reminders fire from scheduler worker threads
without touching the audio subsystem.
"""
from __future__ import annotations

import queue
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional


@dataclass(frozen=True)
class NotificationMessage:
    """An immutable, presentation-agnostic reminder notification."""

    reminder_id: str
    title: str
    description: str
    repeat_type: str
    fired_at: datetime

    def summary(self) -> str:
        """A short human-readable line, e.g. for TTS or a toast."""
        return f"{self.title}: {self.description}" if self.description else self.title


class NotificationQueue:
    """Thread-safe FIFO queue of :class:`NotificationMessage` objects.

    Thin wrapper over :class:`queue.Queue` so the rest of the system depends on
    a small, intention-revealing interface rather than the stdlib type.
    """

    def __init__(self, maxsize: int = 0) -> None:
        self._queue: "queue.Queue[NotificationMessage]" = queue.Queue(maxsize=maxsize)

    def put(self, message: NotificationMessage) -> None:
        """Enqueues a notification (blocks only if a bounded queue is full)."""
        self._queue.put(message)

    def get(
        self, block: bool = True, timeout: Optional[float] = None
    ) -> NotificationMessage:
        """Removes and returns the next notification.

        Raises :class:`queue.Empty` if ``block`` is False / ``timeout`` elapses.
        """
        return self._queue.get(block=block, timeout=timeout)

    def get_nowait(self) -> NotificationMessage:
        """Non-blocking :meth:`get`; raises :class:`queue.Empty` if empty."""
        return self._queue.get_nowait()

    def drain(self) -> List[NotificationMessage]:
        """Removes and returns all currently queued notifications."""
        items: List[NotificationMessage] = []
        while True:
            try:
                items.append(self._queue.get_nowait())
            except queue.Empty:
                break
        return items

    def task_done(self) -> None:
        """Marks a fetched task as processed (mirrors :meth:`queue.Queue.task_done`)."""
        self._queue.task_done()

    def qsize(self) -> int:
        """Approximate number of queued notifications."""
        return self._queue.qsize()

    def __len__(self) -> int:
        return self._queue.qsize()
