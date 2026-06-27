"""Zara Notification subsystem.

Delivers queued notifications to the speaker one at a time, in FIFO order,
without ever interrupting speech that is already in progress.

Pipeline::

    enqueue(notification)
          |
          v
    [ NotificationQueue ]  (thread-safe FIFO)
          |
          v
    NotificationWorker.process()   -- background daemon thread
          |
          v
    Speaker.speak(text)            -- holds a lock: no interruption
          |
          v
    TTS / hardware speaker

Public API:
    Notification              -- a speakable message
    NotificationQueue         -- thread-safe FIFO (enqueue/dequeue)
    Speaker / TTSSpeaker / ConsoleSpeaker -- output adapters (lock-guarded)
    NotificationWorker        -- enqueue() / dequeue() / process() + start/stop
"""
from notifications.config import NotificationConfig
from notifications.models import Notification, Speakable
from notifications.queue import NotificationQueue
from notifications.speaker import Speaker, TTSSpeaker, ConsoleSpeaker
from notifications.toast import (
    DesktopNotifier,
    WindowsToastNotifier,
    ConsoleToastNotifier,
    create_desktop_notifier,
)
from notifications.worker import NotificationWorker

__all__ = [
    "NotificationConfig",
    "Notification",
    "Speakable",
    "NotificationQueue",
    "Speaker",
    "TTSSpeaker",
    "ConsoleSpeaker",
    "DesktopNotifier",
    "WindowsToastNotifier",
    "ConsoleToastNotifier",
    "create_desktop_notifier",
    "NotificationWorker",
]
