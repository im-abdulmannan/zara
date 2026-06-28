"""VAD-based utterance recording (backward-compatible facade).

Delegates to :class:`voice.vad_listener.VadListener`. New code should use
:class:`core.orchestrator.VoiceOrchestrator` and the event bus instead.
"""
from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Callable, Optional

import numpy as np

from voice.config import DEFAULT_LISTENING_CONFIG, ListeningConfig
from voice.vad_listener import CapturePhase, CaptureResult, VadListener


class RecordingPhase(enum.Enum):
    """Legacy phase names (mirrors :class:`CapturePhase`)."""

    WAITING_FOR_SPEECH = "waiting_for_speech"
    RECORDING = "recording"
    COMPLETE = "complete"
    TIMED_OUT = "timed_out"


@dataclass
class RecordingResult:
    """Outcome of a single :meth:`UtteranceRecorder.record` call."""

    audio: Optional[np.ndarray]
    phase: RecordingPhase
    duration_sec: float = 0.0

    @property
    def succeeded(self) -> bool:
        return self.audio is not None and self.phase is RecordingPhase.COMPLETE

    @classmethod
    def from_capture(cls, result: CaptureResult) -> "RecordingResult":
        return cls(
            audio=result.audio,
            phase=RecordingPhase(result.phase.value),
            duration_sec=result.duration_sec,
        )


@dataclass
class UtteranceRecorder:
    """Record one user utterance using voice-activity detection."""

    config: ListeningConfig = field(default_factory=lambda: DEFAULT_LISTENING_CONFIG)
    on_phase_change: Callable[[RecordingPhase], None] | None = None
    minimum_speech_duration: float = 0.3

    def __post_init__(self) -> None:
        phase_cb = self.on_phase_change

        def _wrap_phase(phase: CapturePhase) -> None:
            if phase_cb is not None:
                phase_cb(RecordingPhase(phase.value))

        self._listener = VadListener(
            config=self.config,
            on_phase_change=_wrap_phase if phase_cb else None,
            minimum_speech_duration=self.minimum_speech_duration,
        )

    def record(
        self,
        *,
        wait_for_speech: bool = True,
        initial_wait_timeout: float | None = None,
    ) -> RecordingResult:
        result = self._listener.capture(
            wait_for_speech=wait_for_speech,
            initial_wait_timeout=initial_wait_timeout,
        )
        return RecordingResult.from_capture(result)


def record_utterance(
    *,
    wait_for_speech: bool = True,
    initial_wait_timeout: float | None = None,
    config: ListeningConfig | None = None,
) -> Optional[np.ndarray]:
    """Convenience wrapper that returns PCM audio or ``None`` on timeout."""
    recorder = UtteranceRecorder(config=config or DEFAULT_LISTENING_CONFIG)
    result = recorder.record(
        wait_for_speech=wait_for_speech,
        initial_wait_timeout=initial_wait_timeout,
    )
    return result.audio
