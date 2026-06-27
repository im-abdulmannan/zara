"""Speech-to-text via faster-whisper."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
from faster_whisper import WhisperModel

from voice.config import DEFAULT_LISTENING_CONFIG, ListeningConfig


@dataclass
class WhisperTranscriber:
    """Transcribe PCM audio with a loaded Whisper model."""

    model_size: str = "base"
    device: str = "cpu"
    compute_type: str = "int8"
    language: str = "en"
    config: ListeningConfig = field(default_factory=lambda: DEFAULT_LISTENING_CONFIG)
    _model: WhisperModel | None = field(default=None, init=False, repr=False)

    def _get_model(self) -> WhisperModel:
        if self._model is None:
            self._model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type,
            )
        return self._model

    def transcribe(self, audio: np.ndarray) -> str:
        """Return normalized lowercase text for *audio* (int16 mono PCM)."""
        if audio is None or audio.size == 0:
            return ""

        # faster-whisper expects float32 samples in [-1, 1].
        samples = audio.astype(np.float32) / np.iinfo(np.int16).max
        segments, _info = self._get_model().transcribe(
            samples,
            language=self.language,
        )
        text = " ".join(segment.text for segment in segments).strip()
        return text.lower()


# Shared default transcriber — lazy-loads the model on first use.
_default_transcriber = WhisperTranscriber()


def transcribe(audio: np.ndarray) -> str:
    """Transcribe *audio* using the shared Whisper model."""
    text = _default_transcriber.transcribe(audio)
    print("You:", text)
    return text


def listen() -> str:
    """Backward-compatible helper: record one utterance and transcribe it.

    Prefer :class:`voice.session.VoiceSession` for the full wake-word loop.
    """
    from voice.listener import record_utterance

    audio = record_utterance(wait_for_speech=False)
    if audio is None:
        return ""
    return transcribe(audio)
