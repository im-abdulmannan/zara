"""Background notification worker.

Owns the queue and the speaker and drives the delivery pipeline::

    enqueue(notification) -> [queue] -> process() -> speaker.speak() -> TTS

A single worker thread consumes the queue, which gives FIFO ordering and
one-at-a-time delivery for free. The speaker's lock additionally prevents the
worker from interrupting (or being interrupted by) any other speech in the app.
"""
from __future__ import annotations

import threading
from typing import Optional

from automation.logging_config import get_logger
from notifications.config import NotificationConfig
from notifications.models import to_notification_parts, to_speech_text
from notifications.queue import NotificationQueue
from notifications.speaker import Speaker
from notifications.toast import DesktopNotifier


class NotificationWorker:
    """Consumes queued notifications and speaks them safely in the background."""

    def __init__(
        self,
        speaker: Speaker,
        notification_queue: Optional[NotificationQueue] = None,
        config: Optional[NotificationConfig] = None,
        desktop_notifier: Optional[DesktopNotifier] = None,
    ) -> None:
        """Wires the worker.

        Args:
            speaker: Output adapter (lock-guarded) that renders text to speech.
            notification_queue: FIFO queue; a new one is created if omitted.
            config: Tunables; loaded from the environment if omitted.
            desktop_notifier: Optional popup channel shown alongside speech.
                Its ``notify()`` must be non-blocking. When omitted, only voice
                is used.
        """
        self._config = config or NotificationConfig.from_env()
        self._logger = get_logger(__name__, self._config.log_level)
        self._speaker = speaker
        self._desktop_notifier = desktop_notifier
        self._queue = notification_queue or NotificationQueue(
            maxsize=self._config.queue_maxsize
        )
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    # -- public queue API --------------------------------------------------
    def enqueue(self, notification: object) -> None:
        """Adds a notification to the FIFO queue. Safe to call from any thread."""
        self._queue.enqueue(notification)
        self._logger.debug("Enqueued notification; queue size=%d.", len(self._queue))

    def dequeue(self, timeout: Optional[float] = None) -> Optional[object]:
        """Removes and returns the next notification, or ``None`` if none ready."""
        return self._queue.dequeue(timeout=timeout)

    def process(self, timeout: Optional[float] = None) -> bool:
        """Processes a single notification: dequeue -> resolve text -> speak.

        Blocks up to ``timeout`` (defaults to the configured poll timeout)
        waiting for an item. Returns True if a notification was spoken, False if
        the queue was empty. Exceptions from the speaker are caught and logged
        so one bad notification never kills the worker.
        """
        wait = self._config.poll_timeout if timeout is None else timeout
        item = self._queue.dequeue(timeout=wait)
        if item is None:
            return False
        try:
            text = to_speech_text(item)
            self._logger.info("Processing notification: %r", text)
            # Show the desktop toast first (non-blocking, own thread), so the
            # popup appears as speech begins rather than after it ends.
            if self._desktop_notifier is not None:
                try:
                    title, body = to_notification_parts(item)
                    self._desktop_notifier.notify(title, body)
                except Exception:  # noqa: BLE001 -- toast must not block voice
                    self._logger.exception("Desktop notification failed.")
            # speaker.speak() holds the speech lock for its full duration, so
            # this blocks if anything else is currently speaking -> no interrupt.
            self._speaker.speak(text)
            return True
        except Exception:  # noqa: BLE001 -- isolate one notification's failure
            self._logger.exception("Failed to process a notification.")
            return False
        finally:
            self._queue.task_done()

    # -- background lifecycle ---------------------------------------------
    def start(self) -> None:
        """Starts the background worker thread (idempotent)."""
        if self._thread is not None and self._thread.is_alive():
            self._logger.debug("Worker already running; start() ignored.")
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run, name="notification-worker", daemon=True
        )
        self._thread.start()
        self._logger.info("Notification worker started.")

    def stop(self, wait: bool = True) -> None:
        """Signals the worker to stop and (optionally) joins the thread."""
        self._stop.set()
        thread = self._thread
        if wait and thread is not None:
            thread.join(timeout=self._config.shutdown_timeout)
            if thread.is_alive():
                self._logger.warning("Worker thread did not stop within timeout.")
        self._thread = None
        self._logger.info("Notification worker stopped.")

    def _run(self) -> None:
        """Worker loop: repeatedly process notifications until stopped."""
        self._logger.debug("Worker loop entered.")
        while not self._stop.is_set():
            # process() blocks for poll_timeout, so the stop flag is checked
            # at most poll_timeout seconds after being set.
            self.process()
        self._logger.debug("Worker loop exited.")

    # -- introspection -----------------------------------------------------
    @property
    def is_running(self) -> bool:
        """True while the background thread is alive."""
        return self._thread is not None and self._thread.is_alive()

    @property
    def is_speaking(self) -> bool:
        """True while the speaker is currently producing an utterance."""
        return self._speaker.is_speaking

    @property
    def pending(self) -> int:
        """Approximate number of notifications waiting in the queue."""
        return len(self._queue)
