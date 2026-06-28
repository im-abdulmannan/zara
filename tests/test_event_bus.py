"""Tests for the internal event bus."""
from __future__ import annotations

from core.event_bus import Event, EventBus, EventType


def test_subscribe_and_emit():
    bus = EventBus()
    received = []

    def handler(event: Event) -> None:
        received.append(event)

    bus.subscribe(EventType.WAKE_DETECTED, handler)
    bus.emit(Event(type=EventType.WAKE_DETECTED, source="test", payload={"text": "zara"}))

    assert len(received) == 1
    assert received[0].payload["text"] == "zara"


def test_decorator_registration():
    bus = EventBus()
    received = []

    @bus.on(EventType.ERROR)
    def _on_error(event: Event) -> None:
        received.append(event)

    bus.emit(Event(type=EventType.ERROR, source="test", payload={"error": "boom"}))
    assert len(received) == 1


def test_unsubscribe_removes_handler():
    bus = EventBus()
    received = []

    def handler(event: Event) -> None:
        received.append(event)

    bus.subscribe(EventType.TTS_STARTED, handler)
    bus.unsubscribe(EventType.TTS_STARTED, handler)
    bus.emit(Event(type=EventType.TTS_STARTED, source="test"))

    assert received == []
