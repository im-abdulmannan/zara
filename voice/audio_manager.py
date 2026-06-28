"""Central microphone and audio buffering — sole owner of mic capture."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Generator, Iterator, List, Optional

import numpy as np

from core.logging_config import get_logger
from voice.config import ListeningConfig
from voice.vad import VoiceActivityDetector, create_vad

_logger = get_logger(__name__)


class _MicrophoneBackend:
    """Thin wrapper around sounddevice for testability."""

    def __init__(self, config: ListeningConfig) -> None:
        self._config = config
        self._stream = None

    def start(self) -> None:
        import sounddevice as sd

        self._stream = sd.RawInputStream(
            samplerate=self._config.sample_rate,
            channels=1,
            dtype="int16",
            blocksize=self._config.chunk_samples,
        )
        self._stream.start()
        _logger.debug(
            "Microphone open rate=%s chunk_ms=%s",
            self._config.sample_rate,
            self._config.chunk_ms,
        )

    def stop(self) -> None:
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
            _logger.debug("Microphone closed")

    def read_chunk(self) -> np.ndarray:
        if self._stream is None:
            raise RuntimeError("AudioManager.start() must be called before read_chunk()")
        data, _overflowed = self._stream.read(self._config.chunk_samples)
        return np.frombuffer(data, dtype=np.int16).copy()


class AudioManager:
    """Owns microphone capture, VAD, and in-memory audio buffering.

    Pipeline::

        Microphone -> (future noise suppression) -> VAD -> buffer -> STT

    No other module should open the microphone directly.
    """

    def __init__(
        self,
        config: ListeningConfig,
        vad: VoiceActivityDetector | None = None,
    ) -> None:
        self._config = config
        self._vad = vad or create_vad(config)
        self._mic = _MicrophoneBackend(config)
        self._active = False
        self._buffer: List[np.ndarray] = []

    @property
    def config(self) -> ListeningConfig:
        return self._config

    @property
    def is_active(self) -> bool:
        return self._active

    def start(self) -> None:
        if not self._active:
            self._mic.start()
            self._active = True

    def stop(self) -> None:
        if self._active:
            self._mic.stop()
            self._active = False
            self.clear_buffer()

    def read_frame(self) -> np.ndarray:
        """Read one PCM frame and append it to the internal buffer."""
        frame = self._mic.read_chunk()
        self._buffer.append(frame)
        return frame

    def is_speech(self, frame: np.ndarray) -> bool:
        return self._vad.is_speech(frame)

    def clear_buffer(self) -> None:
        self._buffer.clear()

    def consume_buffer(self) -> Optional[np.ndarray]:
        """Return concatenated buffered audio and clear the buffer."""
        if not self._buffer:
            return None
        audio = np.concatenate(self._buffer)
        self._buffer.clear()
        return audio

    def iter_frames(self) -> Iterator[np.ndarray]:
        """Yield frames until the caller stops iterating."""
        while self._active:
            yield self.read_frame()

    @contextmanager
    def session(self) -> Generator["AudioManager", None, None]:
        """Context manager that opens and closes the microphone."""
        try:
            self.start()
            yield self
        finally:
            self.stop()


# Backward-compatible helpers used by legacy voice.audio consumers.
@contextmanager
def open_microphone(config: ListeningConfig) -> Generator[AudioManager, None, None]:
    """Deprecated: prefer :class:`AudioManager.session`."""
    manager = AudioManager(config)
    with manager.session():
        yield manager
