"""Voice listening configuration.

All timeouts and VAD settings can be overridden via environment variables
or by constructing a :class:`ListeningConfig` directly.
"""
from __future__ import annotations

import os
from dataclasses import dataclass


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return float(raw)


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return int(raw)


@dataclass(frozen=True)
class ListeningConfig:
    """Parameters for VAD-based utterance capture."""

    # Audio capture
    sample_rate: int = 16_000
    chunk_ms: int = 30  # WebRTC VAD supports 10, 20, or 30 ms frames

    # After wake word: max seconds to wait for the user to begin speaking.
    initial_wait_timeout: float = 25.0

    # End utterance after this many seconds of continuous silence once speech
    # has started. Pauses shorter than short_pause_threshold are treated as
    # natural thinking pauses and do not trigger end-of-speech on their own.
    silence_timeout: float = 2.0

    # Pauses shorter than this during an utterance are ignored for end detection.
    short_pause_threshold: float = 1.0

    # WebRTC VAD aggressiveness (0 = least aggressive, 3 = most aggressive).
    vad_aggressiveness: int = 2

    @classmethod
    def from_env(cls) -> "ListeningConfig":
        return cls(
            sample_rate=_env_int("VOICE_SAMPLE_RATE", 16_000),
            chunk_ms=_env_int("VOICE_CHUNK_MS", 30),
            initial_wait_timeout=_env_float("VOICE_INITIAL_WAIT_TIMEOUT", 25.0),
            silence_timeout=_env_float("VOICE_SILENCE_TIMEOUT", 2.0),
            short_pause_threshold=_env_float("VOICE_SHORT_PAUSE_THRESHOLD", 1.0),
            vad_aggressiveness=_env_int("VOICE_VAD_AGGRESSIVENESS", 2),
        )

    @property
    def chunk_samples(self) -> int:
        return int(self.sample_rate * self.chunk_ms / 1000)

    @property
    def frame_duration_sec(self) -> float:
        return self.chunk_ms / 1000.0


DEFAULT_LISTENING_CONFIG = ListeningConfig.from_env()
