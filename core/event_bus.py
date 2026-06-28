"""Internal publish/subscribe event bus for decoupled assistant modules."""
from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any, Callable, DefaultDict, Dict, List

from core.logging_config import get_logger

_logger = get_logger(__name__)

EventHandler = Callable[["Event"], None]


class EventType(enum.Enum):
    """Canonical events exchanged between voice, brain, and runtime layers."""

    WAKE_DETECTED = "wake_detected"
    SPEECH_STARTED = "speech_started"
    SPEECH_FINISHED = "speech_finished"
    TRANSCRIPT_READY = "transcript_ready"
    TOOL_REQUESTED = "tool_requested"
    TOOL_COMPLETED = "tool_completed"
    RESPONSE_READY = "response_ready"
    TTS_STARTED = "tts_started"
    TTS_FINISHED = "tts_finished"
    STATE_CHANGED = "state_changed"
    ERROR = "error"


@dataclass(frozen=True)
class Event:
    """A single bus message with optional structured payload."""

    type: EventType
    payload: Dict[str, Any] = field(default_factory=dict)
    source: str = ""


class EventBus:
    """Synchronous in-process event bus.

    Handlers run in the publisher's thread. This keeps the voice loop simple
    while still allowing modules to react without tight coupling. A future
    streaming or async runtime can swap this for a queue-backed implementation.
    """

    def __init__(self) -> None:
        self._handlers: DefaultDict[EventType, List[EventHandler]] = DefaultDict(list)

    def subscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """Register *handler* for *event_type*."""
        if handler not in self._handlers[event_type]:
            self._handlers[event_type].append(handler)

    def unsubscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """Remove *handler* from *event_type*."""
        try:
            self._handlers[event_type].remove(handler)
        except ValueError:
            pass

    def emit(self, event: Event) -> None:
        """Deliver *event* to all subscribers."""
        _logger.debug(
            "event=%s source=%s keys=%s",
            event.type.value,
            event.source or "-",
            list(event.payload.keys()),
        )
        for handler in list(self._handlers.get(event.type, [])):
            try:
                handler(event)
            except Exception:
                _logger.exception(
                    "Handler failed for event=%s source=%s",
                    event.type.value,
                    event.source,
                )

    def on(self, event_type: EventType) -> Callable[[EventHandler], EventHandler]:
        """Decorator: ``@bus.on(EventType.WAKE_DETECTED)``."""

        def decorator(handler: EventHandler) -> EventHandler:
            self.subscribe(event_type, handler)
            return handler

        return decorator
