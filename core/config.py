"""Central configuration for the event-driven assistant."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Sequence, Tuple

from voice.config import DEFAULT_LISTENING_CONFIG, ListeningConfig, _env_float, _env_int


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class AssistantConfig:
    """Top-level settings for voice flow, session, and orchestration."""

    # Voice / VAD (delegates to :class:`voice.config.ListeningConfig`)
    voice: ListeningConfig = field(default_factory=lambda: DEFAULT_LISTENING_CONFIG)

    # After wake word: seconds to wait for the user to begin speaking.
    wake_timeout: float = 25.0

    # Minimum captured speech duration before accepting an utterance.
    minimum_speech_duration: float = 0.3

    # Energy threshold for the fallback VAD backend.
    vad_energy_threshold: float = 500.0

    # Wake / sleep phrases
    wake_phrases: Tuple[str, ...] = (
        "hello zara",
        "hi zara",
        "hey zara",
        "zara",
    )
    sleep_phrases: Tuple[str, ...] = (
        "sleep zara",
        "go to sleep",
        "you can sleep",
        "goodbye zara",
        "stop listening",
    )

    # Behaviour — after wake, stay in a multi-turn session until sleep or idle timeout.
    play_wake_acknowledgement: bool = True
    wake_acknowledgement_text: str = "I'm listening."
    return_to_wake_after_turn: bool = False
    continuous_conversation: bool = True

    @classmethod
    def from_env(
        cls,
        *,
        wake_word: str | None = None,
        extra_wake_phrases: Sequence[str] = (),
    ) -> "AssistantConfig":
        voice = ListeningConfig.from_env()
        wake_phrases = [
            "hello zara",
            "hi zara",
            "hey zara",
            "zara",
        ]
        if wake_word and wake_word.strip().lower() not in wake_phrases:
            wake_phrases.append(wake_word.strip().lower())
        for phrase in extra_wake_phrases:
            normalized = phrase.strip().lower()
            if normalized and normalized not in wake_phrases:
                wake_phrases.append(normalized)

        return cls(
            voice=voice,
            wake_timeout=_env_float("WAKE_TIMEOUT", voice.initial_wait_timeout),
            minimum_speech_duration=_env_float("MINIMUM_SPEECH_DURATION", 0.3),
            vad_energy_threshold=_env_float("VAD_ENERGY_THRESHOLD", 500.0),
            wake_phrases=tuple(wake_phrases),
            play_wake_acknowledgement=_env_bool("PLAY_WAKE_ACK", True),
            wake_acknowledgement_text=os.getenv(
                "WAKE_ACK_TEXT", "I'm listening."
            ),
            return_to_wake_after_turn=not _env_bool("CONTINUOUS_CONVERSATION", True),
            continuous_conversation=_env_bool("CONTINUOUS_CONVERSATION", True),
        )
