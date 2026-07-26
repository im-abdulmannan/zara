from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable, Optional, Sequence

import numpy as np

from core.logging_config import get_logger
from voice.streaming_wake import StreamingWakeDetector

_logger = get_logger(__name__)

_PUNCT_RE = re.compile(r"[^\w\s']+")


def _normalize_utterance(text: str) -> str:
    cleaned = (text or "").lower().strip()
    cleaned = cleaned.replace("\u2019", "'").replace("\u2018", "'")
    cleaned = _PUNCT_RE.sub(" ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


@dataclass
class WakeWordDetector:
    """Match spoken transcripts or raw PCM audio streams against wake phrases."""

    phrases: Sequence[str] = field(default_factory=tuple)
    sleep_phrases: Sequence[str] = field(default_factory=tuple)
    use_streaming: bool = True
    streaming_threshold: float = 0.5
    streaming_models: Sequence[str] = ()

    _streaming_detector: Optional[StreamingWakeDetector] = field(
        default=None, init=False, repr=False
    )

    def __post_init__(self) -> None:
        if self.use_streaming:
            detector = StreamingWakeDetector(
                target_models=self.streaming_models,
                threshold=self.streaming_threshold,
                enabled=True,
            )
            if detector.enabled:
                self._streaming_detector = detector

    @property
    def has_streaming(self) -> bool:
        """Return True if real-time streaming wake engine is active."""
        return self._streaming_detector is not None and self._streaming_detector.enabled

    def check_streaming_frame(self, frame: np.ndarray) -> bool:
        """Check a raw 16kHz PCM audio frame against openwakeword ONNX model."""
        if self._streaming_detector is not None:
            return self._streaming_detector.is_wake_triggered(frame)
        return False

    def reset_streaming(self) -> None:
        """Clear openwakeword buffers after a wake event."""
        if self._streaming_detector is not None:
            self._streaming_detector.reset()

    def is_wake(self, text: str) -> bool:
        """Return True when *text* matches a wake phrase (and is not a sleep command)."""
        if self.is_sleep(text):
            return False
        matched = self._matches_phrase(text, self.phrases, short_token_exact=True)
        if matched:
            _logger.info("Wake word detected in: %r", text)
        return matched

    def is_sleep(self, text: str) -> bool:
        """Return True when *text* contains a sleep phrase."""
        return self._matches_phrase(text, self.sleep_phrases, short_token_exact=False)

    def extract_command_after_wake(self, text: str) -> str:
        """Return residual command after a wake phrase, else empty string.

        Example: ``hey zara, how are you?`` → ``how are you``.
        """
        normalized = _normalize_utterance(text)
        if not normalized:
            return ""
        # Prefer longer phrases first so "hey zara" wins over bare "zara".
        phrases = sorted(
            (_normalize_utterance(p) for p in self.phrases),
            key=len,
            reverse=True,
        )
        for phrase in phrases:
            if not phrase:
                continue
            pattern = r"(?<!\w)" + re.escape(phrase) + r"(?!\w)\s*(.*)$"
            match = re.search(pattern, normalized)
            if not match:
                continue
            remainder = (match.group(1) or "").strip(" .,!?;:")
            return remainder
        return ""

    @staticmethod
    def _matches_phrase(
        text: str,
        phrases: Iterable[str],
        *,
        short_token_exact: bool,
    ) -> bool:
        normalized = _normalize_utterance(text)
        if not normalized:
            return False

        for phrase in phrases:
            phrase_norm = _normalize_utterance(phrase)
            if not phrase_norm:
                continue
            tokens = phrase_norm.split()
            # Bare short names like "zara" only match as the whole utterance
            # (or utterance starting with that name + trailing filler).
            if short_token_exact and len(tokens) == 1 and len(phrase_norm) <= 8:
                if normalized == phrase_norm or normalized.startswith(phrase_norm + " "):
                    # Reject if it is clearly "sleep/goodbye <name>"
                    first = normalized.split(" ", 1)[0]
                    if first in {"sleep", "goodbye", "stop"}:
                        continue
                    return True
                continue

            pattern = r"(?<!\w)" + re.escape(phrase_norm) + r"(?!\w)"
            if re.search(pattern, normalized):
                return True
        return False
