"""Intent domain model and classification result."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping


class Intent(str, Enum):
    """Supported user-request intents."""

    CHAT = "CHAT"
    REMINDER_CREATE = "REMINDER_CREATE"
    REMINDER_DELETE = "REMINDER_DELETE"
    MEETING_CREATE = "MEETING_CREATE"
    MEETING_QUERY = "MEETING_QUERY"
    NOTE_CREATE = "NOTE_CREATE"
    NOTE_QUERY = "NOTE_QUERY"
    MEMORY_SAVE = "MEMORY_SAVE"
    MEMORY_QUERY = "MEMORY_QUERY"
    HABIT_CREATE = "HABIT_CREATE"
    HABIT_QUERY = "HABIT_QUERY"
    HABIT_DONE = "HABIT_DONE"
    OPEN_APPLICATION = "OPEN_APPLICATION"
    WEB_SEARCH = "WEB_SEARCH"
    SYSTEM_COMMAND = "SYSTEM_COMMAND"

    @classmethod
    def from_value(cls, value: "str | Intent") -> "Intent":
        if isinstance(value, cls):
            return value
        normalised = str(value).strip().upper()
        for member in cls:
            if member.value == normalised:
                return member
        return cls.CHAT


@dataclass(frozen=True)
class ClassificationResult:
    """Structured output from the intent classifier."""

    intent: Intent
    confidence: float
    entities: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "intent": self.intent.value,
            "confidence": round(self.confidence, 4),
            "entities": dict(self.entities),
        }

    @classmethod
    def chat_fallback(cls, *, confidence: float = 0.0) -> "ClassificationResult":
        return cls(intent=Intent.CHAT, confidence=confidence, entities={})
