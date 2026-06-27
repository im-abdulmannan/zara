"""Microphone capture utilities."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Generator, Iterator

import numpy as np
import sounddevice as sd

from voice.config import ListeningConfig


class MicrophoneStream:
    """Blocking PCM capture from the default input device."""

    def __init__(self, config: ListeningConfig) -> None:
        self._config = config
        self._stream: sd.RawInputStream | None = None

    @property
    def chunk_samples(self) -> int:
        return self._config.chunk_samples

    def start(self) -> None:
        self._stream = sd.RawInputStream(
            samplerate=self._config.sample_rate,
            channels=1,
            dtype="int16",
            blocksize=self._config.chunk_samples,
        )
        self._stream.start()

    def stop(self) -> None:
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None

    def read_chunk(self) -> np.ndarray:
        if self._stream is None:
            raise RuntimeError("MicrophoneStream.start() must be called before read_chunk()")

        data, _overflowed = self._stream.read(self._config.chunk_samples)
        return np.frombuffer(data, dtype=np.int16).copy()

    def __enter__(self) -> "MicrophoneStream":
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.stop()


@contextmanager
def open_microphone(config: ListeningConfig) -> Generator[MicrophoneStream, None, None]:
    """Context manager that opens and closes the microphone stream."""
    mic = MicrophoneStream(config)
    try:
        mic.start()
        yield mic
    finally:
        mic.stop()


def iter_audio_chunks(mic: MicrophoneStream) -> Iterator[np.ndarray]:
    """Yield audio frames until the caller stops iterating."""
    while True:
        yield mic.read_chunk()
