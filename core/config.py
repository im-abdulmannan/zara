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

    # Wake / sleep phrases — prefer multi-word phrases; bare names are too sensitive.
    wake_phrases: Tuple[str, ...] = (
        "hello zara",
        "hi zara",
        "hey zara",
        "ok zara",
        "okay zara",
    )
    sleep_phrases: Tuple[str, ...] = (
        "sleep zara",
        "go to sleep",
        "you can sleep",
        "goodbye zara",
        "stop listening",
    )

    # Streaming openwakeword models are Alexa/Jarvis/Mycroft — off by default so Zara
    # only opens on "Hey Zara" / "Hi Zara" via STT.
    use_streaming_wake: bool = False
    streaming_wake_threshold: float = 0.8
    streaming_wake_models: Tuple[str, ...] = ()
    # Pause after "I'm listening" so TTS/echo is not captured as the command.
    post_wake_listen_delay_sec: float = 0.45

    # Behaviour — after wake, stay in a multi-turn session until sleep or idle timeout.
    play_wake_acknowledgement: bool = True
    wake_acknowledgement_text: str = "I'm listening."
    return_to_wake_after_turn: bool = False
    continuous_conversation: bool = True

    # Interrupt TTS when user speech is detected during replies.
    # Default off: laptop speakers often echo into the mic and cut replies short.
    use_barge_in: bool = False

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
            "ok zara",
            "okay zara",
        ]
        # Prefer "hey zara" style. A bare name from WAKE_WORD is still allowed
        # but WakeWordDetector only matches it as a whole utterance.
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
            use_streaming_wake=_env_bool("USE_STREAMING_WAKE", False),
            streaming_wake_threshold=_env_float("STREAMING_WAKE_THRESHOLD", 0.8),
            post_wake_listen_delay_sec=_env_float("POST_WAKE_LISTEN_DELAY", 0.45),
            play_wake_acknowledgement=_env_bool("PLAY_WAKE_ACK", True),
            wake_acknowledgement_text=os.getenv(
                "WAKE_ACK_TEXT", "I'm listening."
            ),
            return_to_wake_after_turn=not _env_bool("CONTINUOUS_CONVERSATION", True),
            continuous_conversation=_env_bool("CONTINUOUS_CONVERSATION", True),
            use_barge_in=_env_bool("USE_BARGE_IN", False),
        )
