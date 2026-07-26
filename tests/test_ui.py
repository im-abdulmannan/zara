"""Unit tests for Zara PySide6 UI overlay and bridge."""
from __future__ import annotations

import os
import pytest
from PySide6.QtWidgets import QApplication

from core.event_bus import Event, EventBus, EventType
from core.state_manager import AssistantState
from ui.bridge import UIEventBridge
from ui.visualizer import VoiceVisualizerWidget


@pytest.fixture(scope="module")
def qapp():
    """Ensure QApplication exists for headless Qt widget tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


def test_voice_visualizer_state_update(qapp):
    widget = VoiceVisualizerWidget()
    widget.set_state(AssistantState.LISTENING)
    assert widget._state == AssistantState.LISTENING

    widget.set_state(AssistantState.THINKING)
    assert widget._state == AssistantState.THINKING


def test_status_store_updates():
    from api.status_store import get_status, update_status

    update_status(state="listening", subtitle="Hello")
    status = get_status()
    assert status["state"] == "listening"
    assert status["subtitle"] == "Hello"


def test_ui_event_bridge_signals(qapp):
    bus = EventBus()
    bridge = UIEventBridge(bus)

    received_states = []
    received_transcripts = []

    bridge.state_changed_signal.connect(lambda s: received_states.append(s))
    bridge.transcript_signal.connect(lambda t: received_transcripts.append(t))

    bus.emit(Event(type=EventType.STATE_CHANGED, source="test", payload={"to": AssistantState.SPEAKING}))
    bus.emit(Event(type=EventType.TRANSCRIPT_READY, source="test", payload={"text": "Open Chrome"}))

    assert AssistantState.SPEAKING in received_states
    assert "\" Open Chrome \"" in received_transcripts


def test_tray_continuous_action_emits(qapp):
    from ui.tray import SystemTrayManager

    tray = SystemTrayManager()
    seen = []
    tray.toggle_continuous_signal.connect(lambda: seen.append(True))
    tray.continuous_action.trigger()
    assert seen
    tray._icon.hide()
