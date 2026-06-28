"""Conversation session tracking for multi-turn interactions."""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Session:
    """Mutable session context shared across voice turns.

    Designed for long-running conversations, tool chaining, and future
    interrupt / continuous-conversation modes.
    """

    conversation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    history: List[Dict[str, str]] = field(default_factory=list)
    current_task: Optional[str] = None
    tool_history: List[Dict[str, Any]] = field(default_factory=list)
    last_activity: float = field(default_factory=time.monotonic)
    active_window: Optional[str] = None
    interruptible: bool = True
    continuous_mode: bool = False

    def touch(self) -> None:
        """Record user or assistant activity."""
        self.last_activity = time.monotonic()

    def add_user_turn(self, text: str) -> None:
        self.history.append({"role": "user", "content": text})
        self.touch()

    def add_assistant_turn(self, text: str) -> None:
        self.history.append({"role": "assistant", "content": text})
        self.touch()

    def record_tool(self, name: str, success: bool, message: str) -> None:
        self.tool_history.append(
            {
                "tool": name,
                "success": success,
                "message": message,
                "at": time.monotonic(),
            }
        )
        self.touch()
