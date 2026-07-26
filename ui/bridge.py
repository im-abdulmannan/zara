"""Thread-safe bridge between EventBus and PySide6 Qt Signals."""
from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from core.event_bus import Event, EventBus, EventType
from core.state_manager import AssistantState


class UIEventBridge(QObject):
    """Subscribes to Zara EventBus and emits thread-safe Qt Signals."""

    state_changed_signal = Signal(object)      # AssistantState
    transcript_signal = Signal(str)            # user speech text
    response_signal = Signal(str)              # assistant response text
    error_signal = Signal(str)                 # error message

    def __init__(self, bus: EventBus, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.bus = bus
        self._subscribe_events()

    def _subscribe_events(self) -> None:
        @self.bus.on(EventType.STATE_CHANGED)
        def _on_state_changed(event: Event) -> None:
            new_state = event.payload.get("to")
            if isinstance(new_state, AssistantState):
                self.state_changed_signal.emit(new_state)

        @self.bus.on(EventType.TRANSCRIPT_READY)
        def _on_transcript(event: Event) -> None:
            text = event.payload.get("text", "")
            if text:
                self.transcript_signal.emit(f"\" {text} \"")

        @self.bus.on(EventType.RESPONSE_READY)
        def _on_response(event: Event) -> None:
            text = event.payload.get("text", "")
            if text:
                self.response_signal.emit(text)

        @self.bus.on(EventType.ERROR)
        def _on_error(event: Event) -> None:
            err = event.payload.get("error", "An error occurred")
            self.error_signal.emit(str(err))
