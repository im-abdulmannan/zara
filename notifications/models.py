"""Notification data model.

``Speakable`` is the minimal contract the worker needs: anything that can yield
a line of text to speak. This lets the worker accept a plain
:class:`Notification` *or* a ``reminders.NotificationMessage`` (which already
implements ``summary()``) without coupling the two packages.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Protocol, runtime_checkable


@runtime_checkable
class Speakable(Protocol):
    """Anything that can produce a single line of speakable text."""

    def summary(self) -> str:
        ...


@dataclass(frozen=True)
class Notification:
    """A speakable notification carried through the queue.

    Attributes:
        message: The body to speak.
        title: Optional short label, prepended to the spoken line.
        source: Where it originated (e.g. ``"reminder"``) -- for logging.
        created_at: When it was created (defaults to now).
    """

    message: str
    title: Optional[str] = None
    source: str = "system"
    created_at: datetime = field(default_factory=datetime.now)

    def summary(self) -> str:
        """Returns the line to speak (``"title: message"`` when a title exists)."""
        if self.title:
            return f"{self.title}: {self.message}"
        return self.message


def to_speech_text(item: object) -> str:
    """Resolves an arbitrary queued item into a string for the speaker.

    Accepts a :class:`Speakable` (``summary()``), a plain ``str``, or anything
    with a ``message`` attribute; falls back to ``str(item)``.
    """
    if isinstance(item, Speakable):
        return item.summary()
    if isinstance(item, str):
        return item
    message = getattr(item, "message", None)
    if isinstance(message, str):
        return message
    return str(item)


def to_notification_parts(item: object, default_title: str = "Reminder") -> "tuple[str, str]":
    """Resolves a queued item into ``(title, body)`` for a desktop toast.

    The body is the speakable text. The title is the item's ``title`` when it
    differs from the body, otherwise a generic label (a reminder's title often
    *is* its body, so showing it twice would be redundant).
    """
    body = to_speech_text(item)
    title = getattr(item, "title", None) or default_title
    if str(title) == body:
        title = default_title
    return str(title), body
