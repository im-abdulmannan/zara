"""Conversation history bridging session and persistent memory."""
from __future__ import annotations

from typing import List

from core.logging_config import get_logger
from core.session import Session
from memory.memory import load_history, save_history

_logger = get_logger(__name__)


class ConversationStore:
    """Sync in-memory session history with the on-disk conversation log."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._disk_history = load_history()

    @property
    def messages(self) -> List[dict]:
        return self._disk_history

    def append_user(self, text: str) -> None:
        self._session.add_user_turn(text)
        self._disk_history.append({"role": "user", "content": text})
        save_history(self._disk_history)
        _logger.debug("User turn saved (%d messages)", len(self._disk_history))

    def append_assistant(self, text: str) -> None:
        self._session.add_assistant_turn(text)
        self._disk_history.append({"role": "assistant", "content": text})
        save_history(self._disk_history)
        _logger.debug("Assistant turn saved (%d messages)", len(self._disk_history))
