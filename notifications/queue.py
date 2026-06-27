"""Thread-safe FIFO notification queue.

A thin, intention-revealing wrapper over :class:`queue.Queue`. ``queue.Queue``
is already thread-safe and FIFO, so the value here is a small, named interface
(``enqueue`` / ``dequeue``) that the rest of the system depends on instead of
the stdlib type directly.
"""
from __future__ import annotations

import queue
from typing import List, Optional


class NotificationQueue:
    """Thread-safe, FIFO queue of notifications.

    Any object may be queued; the worker resolves it to speakable text. Use a
    ``maxsize > 0`` to bound memory (enqueue then blocks/raises when full).
    """

    def __init__(self, maxsize: int = 0) -> None:
        self._queue: "queue.Queue[object]" = queue.Queue(maxsize=maxsize)

    def enqueue(self, item: object, block: bool = True, timeout: Optional[float] = None) -> None:
        """Adds ``item`` to the back of the queue (FIFO).

        Raises :class:`queue.Full` if a bounded queue is full and it cannot be
        enqueued within ``timeout``.
        """
        self._queue.put(item, block=block, timeout=timeout)

    def dequeue(self, block: bool = True, timeout: Optional[float] = None) -> Optional[object]:
        """Removes and returns the item at the front of the queue.

        Returns ``None`` instead of raising when the queue is empty (after
        ``timeout``), so worker loops can poll without exception handling.
        """
        try:
            return self._queue.get(block=block, timeout=timeout)
        except queue.Empty:
            return None

    def task_done(self) -> None:
        """Signals that a dequeued item has been fully processed."""
        self._queue.task_done()

    def join(self) -> None:
        """Blocks until every enqueued item has been marked done."""
        self._queue.join()

    def drain(self) -> List[object]:
        """Removes and returns all currently queued items (non-blocking)."""
        items: List[object] = []
        while True:
            item = self.dequeue(block=False)
            if item is None:
                break
            items.append(item)
        return items

    def empty(self) -> bool:
        return self._queue.empty()

    def size(self) -> int:
        return self._queue.qsize()

    def __len__(self) -> int:
        return self._queue.qsize()
