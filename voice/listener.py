"""VAD-based utterance recording.

Captures a single spoken utterance using a small state machine:

    WAIT_FOR_SPEECH  ->  RECORDING  ->  DONE

There is no fixed recording window. Recording starts when speech is first
detected and ends only after ``silence_timeout`` seconds of continuous
silence (pauses under ``short_pause_threshold`` are treated as thinking).

Future hooks (interrupt during TTS, continuous conversation, streaming STT)
can wrap or subclass :class:`UtteranceRecorder` without changing this core.
"""
from __future__ import annotations

import enum
import time
from dataclasses import dataclass, field
from typing import Callable, List, Optional

import numpy as np

from voice.audio import MicrophoneStream, open_microphone
from voice.config import DEFAULT_LISTENING_CONFIG, ListeningConfig
from voice.vad import VoiceActivityDetector, create_vad


class RecordingPhase(enum.Enum):
    """Internal phases while waiting for or capturing an utterance."""

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


@dataclass
class UtteranceRecorder:
    """Record one user utterance using voice-activity detection."""

    config: ListeningConfig = field(default_factory=lambda: DEFAULT_LISTENING_CONFIG)
    vad: VoiceActivityDetector | None = None
    on_phase_change: Callable[[RecordingPhase], None] | None = None

    def __post_init__(self) -> None:
        if self.vad is None:
            self.vad = create_vad(self.config)

    def record(
        self,
        *,
        wait_for_speech: bool = True,
        initial_wait_timeout: float | None = None,
    ) -> RecordingResult:
        """Capture one utterance from the microphone.

        Parameters
        ----------
        wait_for_speech:
            When True, keep listening until speech is detected or
            ``initial_wait_timeout`` elapses. When False, wait indefinitely
            for the first speech (useful for wake-word listening).
        initial_wait_timeout:
            Seconds to wait for speech to begin. Defaults to
            ``config.initial_wait_timeout``. Pass ``None`` to wait forever.
        """
        if initial_wait_timeout is None and wait_for_speech:
            initial_wait_timeout = self.config.initial_wait_timeout
        elif not wait_for_speech:
            initial_wait_timeout = None

        started = time.monotonic()
        phase = RecordingPhase.WAITING_FOR_SPEECH
        self._notify_phase(phase)

        chunks: List[np.ndarray] = []
        speech_started = False
        silence_sec = 0.0

        with open_microphone(self.config) as mic:
            while True:
                frame = mic.read_chunk()
                now = time.monotonic()
                elapsed = now - started
                is_speech = self.vad.is_speech(frame)

                if phase is RecordingPhase.WAITING_FOR_SPEECH:
                    if (
                        initial_wait_timeout is not None
                        and elapsed >= initial_wait_timeout
                    ):
                        self._notify_phase(RecordingPhase.TIMED_OUT)
                        return RecordingResult(
                            audio=None,
                            phase=RecordingPhase.TIMED_OUT,
                            duration_sec=elapsed,
                        )

                    if is_speech:
                        phase = RecordingPhase.RECORDING
                        speech_started = True
                        silence_sec = 0.0
                        chunks.append(frame)
                        self._notify_phase(phase)
                    continue

                # RECORDING — append every frame so brief pauses are preserved.
                chunks.append(frame)

                if is_speech:
                    speech_started = True
                    silence_sec = 0.0
                    continue

                if not speech_started:
                    # Ignore leading silence after the wait phase ended.
                    chunks.clear()
                    continue

                silence_sec += self.config.frame_duration_sec

                # Natural pauses under short_pause_threshold never end the
                # utterance; end only after silence_timeout continuous silence.
                if silence_sec >= self.config.silence_timeout:
                    self._notify_phase(RecordingPhase.COMPLETE)
                    audio = np.concatenate(chunks) if chunks else None
                    return RecordingResult(
                        audio=audio,
                        phase=RecordingPhase.COMPLETE,
                        duration_sec=time.monotonic() - started,
                    )

    def _notify_phase(self, phase: RecordingPhase) -> None:
        if self.on_phase_change is not None:
            self.on_phase_change(phase)


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
