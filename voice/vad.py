"""Voice Activity Detection (VAD) abstraction.

The default implementation wraps WebRTC VAD (via ``webrtcvad-wheels`` on
Windows). If WebRTC is unavailable, falls back to a lightweight energy-based
detector so the assistant still runs without a C compiler.
"""
from __future__ import annotations

from typing import Protocol

import numpy as np

try:
    import webrtcvad
except ImportError:  # pragma: no cover - optional dependency
    webrtcvad = None  # type: ignore[assignment]


class VoiceActivityDetector(Protocol):
    """Detect speech in a single PCM audio frame."""

    def is_speech(self, frame: np.ndarray) -> bool:
        """Return True when *frame* contains speech."""
        ...


class WebRtcVoiceActivityDetector:
    """Frame-based VAD using Google's WebRTC implementation."""

    def __init__(self, sample_rate: int, aggressiveness: int = 2) -> None:
        if webrtcvad is None:
            raise RuntimeError(
                "webrtcvad is not installed. Run: pip install webrtcvad-wheels"
            )
        if sample_rate not in (8_000, 16_000, 32_000):
            raise ValueError(
                f"WebRTC VAD requires sample rate 8000, 16000, or 32000; got {sample_rate}"
            )
        if aggressiveness not in range(4):
            raise ValueError("aggressiveness must be 0..3")

        self._sample_rate = sample_rate
        self._vad = webrtcvad.Vad(aggressiveness)

    @property
    def sample_rate(self) -> int:
        return self._sample_rate

    def is_speech(self, frame: np.ndarray) -> bool:
        if frame.dtype != np.int16:
            frame = frame.astype(np.int16)

        # WebRTC VAD expects raw 16-bit mono PCM bytes.
        return self._vad.is_speech(frame.tobytes(), self._sample_rate)


class EnergyVoiceActivityDetector:
    """Simple RMS energy fallback when WebRTC VAD is unavailable."""

    def __init__(self, sample_rate: int, energy_threshold: float = 500.0) -> None:
        self._sample_rate = sample_rate
        self._energy_threshold = energy_threshold

    @property
    def sample_rate(self) -> int:
        return self._sample_rate

    def is_speech(self, frame: np.ndarray) -> bool:
        if frame.size == 0:
            return False
        samples = frame.astype(np.float32)
        rms = float(np.sqrt(np.mean(samples * samples)))
        return rms >= self._energy_threshold


def create_vad(config) -> VoiceActivityDetector:
    """Factory for the default production VAD backend."""
    if webrtcvad is not None:
        return WebRtcVoiceActivityDetector(
            sample_rate=config.sample_rate,
            aggressiveness=config.vad_aggressiveness,
        )
    return EnergyVoiceActivityDetector(sample_rate=config.sample_rate)
