"""Zara core: event bus, state machine, session, orchestration."""

from core.config import AssistantConfig
from core.event_bus import Event, EventBus, EventType
from core.session import Session
from core.state_manager import AssistantState, StateManager

__all__ = [
    "AssistantConfig",
    "AssistantState",
    "Event",
    "EventBus",
    "EventType",
    "Session",
    "StateManager",
    "VoiceOrchestrator",
]


def __getattr__(name: str):
    if name == "VoiceOrchestrator":
        from core.orchestrator import VoiceOrchestrator

        return VoiceOrchestrator
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
