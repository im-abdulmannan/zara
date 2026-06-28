"""Event-aware VAD utterance capture built on :class:`AudioManager`."""
from __future__ import annotations

import enum
import time
from dataclasses import dataclass, field
from typing import Callable, List, Optional

import numpy as np

from core.event_bus import Event, EventBus, EventType
from core.logging_config import get_logger
from voice.audio_manager import AudioManager
from voice.config import DEFAULT_LISTENING_CONFIG, ListeningConfig

_logger = get_logger(__name__)


class CapturePhase(enum.Enum):
    """Phases while waiting for or recording speech."""

    WAITING_FOR_SPEECH = "waiting_for_speech"
    RECORDING = "recording"
    COMPLETE = "complete"
    TIMED_OUT = "timed_out"


@dataclass
class CaptureResult:
    """Outcome of a single utterance capture."""

    audio: Optional[np.ndarray]
    phase: CapturePhase
    duration_sec: float = 0.0
    speech_duration_sec: float = 0.0

    @property
    def succeeded(self) -> bool:
        return self.audio is not None and self.phase is CapturePhase.COMPLETE


@dataclass
class VadListener:
    """Capture one user utterance using VAD — no fixed recording window.

    Emits ``SPEECH_STARTED`` and ``SPEECH_FINISHED`` on the event bus when
    configured. Recording begins when speech is first detected and ends only
    after ``silence_timeout`` seconds of continuous silence.
    """

    config: ListeningConfig = field(default_factory=lambda: DEFAULT_LISTENING_CONFIG)
    audio: AudioManager | None = None
    bus: EventBus | None = None
    on_phase_change: Callable[[CapturePhase], None] | None = None
    minimum_speech_duration: float = 0.3

    def __post_init__(self) -> None:
        if self.audio is None:
            self.audio = AudioManager(self.config)

    def capture(
        self,
        *,
        wait_for_speech: bool = True,
        initial_wait_timeout: float | None = None,
    ) -> CaptureResult:
        """Record one utterance from the microphone via VAD."""
        if initial_wait_timeout is None and wait_for_speech:
            initial_wait_timeout = self.config.initial_wait_timeout
        elif not wait_for_speech:
            initial_wait_timeout = None

        started = time.monotonic()
        phase = CapturePhase.WAITING_FOR_SPEECH
        self._notify_phase(phase)

        chunks: List[np.ndarray] = []
        speech_started = False
        silence_sec = 0.0
        speech_frames = 0

        with self.audio.session():
            while True:
                frame = self.audio.read_frame()
                now = time.monotonic()
                elapsed = now - started
                is_speech = self.audio.is_speech(frame)

                if phase is CapturePhase.WAITING_FOR_SPEECH:
                    if (
                        initial_wait_timeout is not None
                        and elapsed >= initial_wait_timeout
                    ):
                        self._notify_phase(CapturePhase.TIMED_OUT)
                        return CaptureResult(
                            audio=None,
                            phase=CapturePhase.TIMED_OUT,
                            duration_sec=elapsed,
                        )

                    if is_speech:
                        phase = CapturePhase.RECORDING
                        speech_started = True
                        silence_sec = 0.0
                        speech_frames = 1
                        chunks.append(frame)
                        self._notify_phase(phase)
                        self._emit(EventType.SPEECH_STARTED, {"elapsed": elapsed})
                    continue

                chunks.append(frame)

                if is_speech:
                    if not speech_started:
                        self._emit(EventType.SPEECH_STARTED, {"elapsed": elapsed})
                    speech_started = True
                    speech_frames += 1
                    silence_sec = 0.0
                    continue

                if not speech_started:
                    chunks.clear()
                    continue

                silence_sec += self.config.frame_duration_sec

                if silence_sec >= self.config.silence_timeout:
                    speech_duration = speech_frames * self.config.frame_duration_sec
                    if speech_duration < self.minimum_speech_duration:
                        _logger.debug(
                            "Utterance too short (%.2fs); discarding",
                            speech_duration,
                        )
                        return CaptureResult(
                            audio=None,
                            phase=CapturePhase.TIMED_OUT,
                            duration_sec=time.monotonic() - started,
                            speech_duration_sec=speech_duration,
                        )

                    self._notify_phase(CapturePhase.COMPLETE)
                    audio = np.concatenate(chunks) if chunks else None
                    result = CaptureResult(
                        audio=audio,
                        phase=CapturePhase.COMPLETE,
                        duration_sec=time.monotonic() - started,
                        speech_duration_sec=speech_duration,
                    )
                    self._emit(
                        EventType.SPEECH_FINISHED,
                        {
                            "duration_sec": result.duration_sec,
                            "speech_duration_sec": speech_duration,
                        },
                    )
                    return result

    def _notify_phase(self, phase: CapturePhase) -> None:
        _logger.debug("capture phase=%s", phase.value)
        if self.on_phase_change is not None:
            self.on_phase_change(phase)

    def _emit(self, event_type: EventType, payload: dict) -> None:
        if self.bus is not None:
            self.bus.emit(
                Event(type=event_type, source="vad_listener", payload=payload)
            )
