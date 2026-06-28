"""Microphone capture utilities (backward-compatible re-exports)."""
from __future__ import annotations

from voice.audio_manager import AudioManager, open_microphone

# Legacy alias — prefer AudioManager.read_frame()
class MicrophoneStream:
    """Deprecated: use :class:`voice.audio_manager.AudioManager`."""

    def __init__(self, config) -> None:
        self._manager = AudioManager(config)

    @property
    def chunk_samples(self) -> int:
        return self._manager.config.chunk_samples

    def start(self) -> None:
        self._manager.start()

    def stop(self) -> None:
        self._manager.stop()

    def read_chunk(self):
        return self._manager.read_frame()


def iter_audio_chunks(mic: MicrophoneStream):
    """Yield audio frames until the caller stops iterating."""
    while True:
        yield mic.read_chunk()


__all__ = ["AudioManager", "MicrophoneStream", "iter_audio_chunks", "open_microphone"]
