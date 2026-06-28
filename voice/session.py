"""High-level voice interaction orchestration (backward-compatible facade).

New integrations should use :class:`core.orchestrator.VoiceOrchestrator`.
"""
from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Callable, Iterable, Optional, Sequence

import numpy as np

from core.logging_config import get_logger
from voice.config import DEFAULT_LISTENING_CONFIG, ListeningConfig
from voice.stt import WhisperTranscriber
from voice.vad_listener import CapturePhase, VadListener
from voice.wake_word import WakeWordDetector

_logger = get_logger(__name__)


class SessionPhase(enum.Enum):
    """User-visible phases in the voice interaction loop."""

    WAITING_FOR_WAKE = "waiting_for_wake"
    READY = "ready"
    LISTENING = "listening"
    PROCESSING = "processing"


@dataclass
class VoiceTurn:
    """One captured and transcribed user utterance."""

    text: str
    audio: np.ndarray
    session_phase: SessionPhase


@dataclass
class VoiceSession:
    """Reusable voice session: wake word -> VAD listen -> transcribe."""

    wake_phrases: Sequence[str]
    sleep_phrases: Sequence[str] = field(default_factory=tuple)
    config: ListeningConfig = field(default_factory=lambda: DEFAULT_LISTENING_CONFIG)
    transcriber: WhisperTranscriber = field(default_factory=WhisperTranscriber)
    return_to_wake_after_turn: bool = True
    on_phase_change: Callable[[SessionPhase], None] | None = None

    def __post_init__(self) -> None:
        self._phase = SessionPhase.WAITING_FOR_WAKE
        self._wake = WakeWordDetector(
            phrases=self.wake_phrases,
            sleep_phrases=self.sleep_phrases,
        )
        self._listener = VadListener(config=self.config)

    @property
    def is_awake(self) -> bool:
        return self._phase in (
            SessionPhase.READY,
            SessionPhase.LISTENING,
            SessionPhase.PROCESSING,
        )

    def wake(self) -> None:
        self._set_phase(SessionPhase.READY)

    def sleep(self) -> None:
        self._set_phase(SessionPhase.WAITING_FOR_WAKE)

    def listen_for_wake(self) -> Optional[VoiceTurn]:
        """Wait indefinitely for speech and check for a wake phrase."""
        self._set_phase(SessionPhase.WAITING_FOR_WAKE)
        _logger.info("Waiting for wake word")

        result = self._listener.capture(wait_for_speech=False)
        if not result.succeeded or result.audio is None:
            return None

        text = self.transcriber.transcribe(result.audio)
        _logger.info("Heard: %r", text)

        if self._wake.is_wake(text):
            self.wake()
            return VoiceTurn(text=text, audio=result.audio, session_phase=SessionPhase.READY)

        return None

    def listen_for_command(self) -> Optional[VoiceTurn]:
        """After wake, wait for the user to speak and return their command."""
        self._set_phase(SessionPhase.READY)
        _logger.info("Ready for command")

        result = self._listener.capture(
            wait_for_speech=True,
            initial_wait_timeout=self.config.initial_wait_timeout,
        )

        if result.phase is CapturePhase.TIMED_OUT:
            _logger.info("No speech detected (initial wait timed out)")
            return None

        if not result.succeeded or result.audio is None:
            return None

        self._set_phase(SessionPhase.LISTENING)
        text = self.transcriber.transcribe(result.audio)
        _logger.info("User command: %r", text)
        return VoiceTurn(
            text=text.strip(),
            audio=result.audio,
            session_phase=SessionPhase.LISTENING,
        )

    def run_wake_cycle(self) -> Optional[VoiceTurn]:
        """One full cycle: wake detection, then command capture."""
        wake_turn = self.listen_for_wake()
        if wake_turn is None:
            return None
        return self.listen_for_command()

    def is_sleep_command(self, text: str) -> bool:
        return self._wake.is_sleep(text)

    def finish_turn(self) -> None:
        """Return to wake-word mode after responding (unless continuous mode)."""
        if self.return_to_wake_after_turn:
            self.sleep()

    def set_phase(self, phase: SessionPhase) -> None:
        """Notify listeners of a session phase change (for UI / logging hooks)."""
        if self.on_phase_change is not None:
            self.on_phase_change(phase)

    def _set_phase(self, phase: SessionPhase) -> None:
        self._phase = phase
        self.set_phase(phase)
