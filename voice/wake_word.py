"""Wake-word detection from transcribed speech."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Sequence

from core.logging_config import get_logger

_logger = get_logger(__name__)


@dataclass
class WakeWordDetector:
    """Match spoken transcripts against configured wake phrases."""

    phrases: Sequence[str] = field(default_factory=tuple)
    sleep_phrases: Sequence[str] = field(default_factory=tuple)

    def is_wake(self, text: str) -> bool:
        """Return True when *text* contains a wake phrase."""
        matched = self._contains_phrase(text, self.phrases)
        if matched:
            _logger.info("Wake word detected in: %r", text)
        return matched

    def is_sleep(self, text: str) -> bool:
        """Return True when *text* contains a sleep phrase."""
        return self._contains_phrase(text, self.sleep_phrases)

    @staticmethod
    def _contains_phrase(text: str, phrases: Iterable[str]) -> bool:
        normalized = text.lower().strip()
        return any(phrase in normalized for phrase in phrases)
