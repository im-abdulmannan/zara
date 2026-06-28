"""Tests for the assistant state machine."""
from __future__ import annotations

from core.event_bus import EventBus, EventType
from core.state_manager import AssistantState, StateManager


def test_initial_state_is_idle():
    bus = EventBus()
    sm = StateManager(bus)
    assert sm.state is AssistantState.IDLE


def test_valid_transition_updates_state():
    bus = EventBus()
    sm = StateManager(bus)
    sm.transition(AssistantState.LISTENING, reason="test")
    assert sm.state is AssistantState.LISTENING


def test_invalid_transition_is_ignored():
    bus = EventBus()
    sm = StateManager(bus)
    sm.transition(AssistantState.THINKING, reason="invalid")
    assert sm.state is AssistantState.IDLE


def test_force_transition_bypasses_rules():
    bus = EventBus()
    sm = StateManager(bus)
    sm.transition(AssistantState.SPEAKING, reason="forced", force=True)
    assert sm.state is AssistantState.SPEAKING


def test_reset_returns_to_idle():
    bus = EventBus()
    sm = StateManager(bus)
    sm.transition(AssistantState.LISTENING, reason="test")
    sm.reset(reason="done")
    assert sm.state is AssistantState.IDLE


def test_state_changed_event_emitted():
    bus = EventBus()
    sm = StateManager(bus)
    events = []

    @bus.on(EventType.STATE_CHANGED)
    def _capture(event):
        events.append(event.payload)

    sm.transition(AssistantState.LISTENING, reason="listen")
    assert len(events) == 1
    assert events[0]["from"] == "idle"
    assert events[0]["to"] == "listening"
    assert events[0]["reason"] == "listen"
