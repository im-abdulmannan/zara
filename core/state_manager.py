"""Explicit assistant state machine — no boolean wake flags."""
from __future__ import annotations

import enum
from typing import FrozenSet, Mapping, Optional, Set

from core.event_bus import Event, EventBus, EventType
from core.logging_config import get_logger

_logger = get_logger(__name__)


class AssistantState(enum.Enum):
    """High-level states for the voice assistant lifecycle."""

    IDLE = "idle"
    WAKE_DETECTED = "wake_detected"
    LISTENING = "listening"
    RECORDING = "recording"
    THINKING = "thinking"
    EXECUTING_TOOL = "executing_tool"
    SPEAKING = "speaking"
    ERROR = "error"


# Allowed transitions: from_state -> {to_states}
_TRANSITIONS: Mapping[AssistantState, FrozenSet[AssistantState]] = {
    AssistantState.IDLE: frozenset(
        {AssistantState.WAKE_DETECTED, AssistantState.LISTENING, AssistantState.ERROR}
    ),
    AssistantState.WAKE_DETECTED: frozenset(
        {AssistantState.LISTENING, AssistantState.SPEAKING, AssistantState.ERROR, AssistantState.IDLE}
    ),
    AssistantState.LISTENING: frozenset(
        {AssistantState.RECORDING, AssistantState.IDLE, AssistantState.ERROR}
    ),
    AssistantState.RECORDING: frozenset(
        {AssistantState.THINKING, AssistantState.LISTENING, AssistantState.IDLE, AssistantState.ERROR}
    ),
    AssistantState.THINKING: frozenset(
        {AssistantState.EXECUTING_TOOL, AssistantState.SPEAKING, AssistantState.ERROR, AssistantState.IDLE}
    ),
    AssistantState.EXECUTING_TOOL: frozenset(
        {AssistantState.SPEAKING, AssistantState.THINKING, AssistantState.ERROR, AssistantState.IDLE}
    ),
    AssistantState.SPEAKING: frozenset(
        {AssistantState.IDLE, AssistantState.LISTENING, AssistantState.ERROR}
    ),
    AssistantState.ERROR: frozenset({AssistantState.IDLE, AssistantState.LISTENING}),
}


class StateManager:
    """Owns the current assistant state and emits ``STATE_CHANGED`` events."""

    def __init__(self, bus: EventBus) -> None:
        self._bus = bus
        self._state = AssistantState.IDLE

    @property
    def state(self) -> AssistantState:
        return self._state

    def can_transition(self, target: AssistantState) -> bool:
        allowed: Set[AssistantState] = set(_TRANSITIONS.get(self._state, frozenset()))
        return target in allowed or target is self._state

    def transition(
        self,
        target: AssistantState,
        *,
        reason: str = "",
        force: bool = False,
    ) -> AssistantState:
        """Move to *target* when allowed; returns the new state."""
        previous = self._state
        if target is previous:
            return previous

        if not force and not self.can_transition(target):
            _logger.warning(
                "Invalid transition %s -> %s (%s); staying in %s",
                previous.value,
                target.value,
                reason,
                previous.value,
            )
            return previous

        self._state = target
        _logger.info(
            "state %s -> %s%s",
            previous.value,
            target.value,
            f" ({reason})" if reason else "",
        )
        self._bus.emit(
            Event(
                type=EventType.STATE_CHANGED,
                source="state_manager",
                payload={
                    "from": previous.value,
                    "to": target.value,
                    "reason": reason,
                },
            )
        )
        return self._state

    def reset(self, *, reason: str = "reset") -> AssistantState:
        """Force return to IDLE (shutdown / recovery)."""
        return self.transition(AssistantState.IDLE, reason=reason, force=True)
