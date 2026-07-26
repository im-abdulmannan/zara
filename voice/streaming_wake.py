"""Real-time streaming wake-word detection using openwakeword ONNX models."""
from __future__ import annotations

import time
from typing import Callable, Iterable, Sequence, Optional
import numpy as np

from core.logging_config import get_logger

_logger = get_logger(__name__)

try:
    import openwakeword
    from openwakeword.model import Model as OWWModel
    HAS_OPENWAKEWORD = True
except ImportError:
    HAS_OPENWAKEWORD = False
    OWWModel = None


class StreamingWakeDetector:
    """Stream PCM frames through openwakeword ONNX models to detect wake phrases.

    Runs on 16kHz mono audio chunks (e.g. 1280 samples / 80ms) without needing
    heavy Speech-To-Text (Whisper) transcription.
    """

    def __init__(
        self,
        target_models: Sequence[str] = ("alexa", "hey_jarvis", "hey_mycroft"),
        threshold: float = 0.5,
        enabled: bool = True,
    ) -> None:
        self.target_models = tuple(target_models)
        self.threshold = threshold
        self.enabled = enabled and HAS_OPENWAKEWORD
        self._model: Optional[OWWModel] = None
        self._hit_streak = 0
        self._required_hits = 3  # consecutive frames above threshold

        if self.enabled:
            try:
                # Try initializing requested ONNX models
                try:
                    self._model = OWWModel(
                        wakeword_models=list(self.target_models) if self.target_models else None,
                        inference_framework="onnx",
                    )
                except Exception as exc:
                    _logger.warning("Initializing openwakeword models failed (%s). Downloading defaults...", exc)
                    openwakeword.utils.download_models()
                    self._model = OWWModel(inference_framework="onnx")

                _logger.info(
                    "Streaming wake-word detector initialized with models: %s",
                    list(self._model.models.keys()) if self._model else [],
                )
            except Exception as err:
                _logger.error("Could not start openwakeword engine: %s", err)
                self.enabled = False

    def predict_frame(self, frame: np.ndarray) -> dict[str, float]:
        """Predict confidence scores for a single audio frame (16kHz PCM)."""
        if not self.enabled or self._model is None:
            return {}

        # Convert float32 [-1, 1] to int16 format if necessary
        if frame.dtype == np.float32 or np.issubdtype(frame.dtype, np.floating):
            pcm16 = (frame * 32767.0).astype(np.int16)
        else:
            pcm16 = frame.astype(np.int16)

        try:
            scores = self._model.predict(pcm16)
            return scores
        except Exception as exc:
            _logger.debug("Error predicting streaming wake score: %s", exc)
            return {}

    def is_wake_triggered(self, frame: np.ndarray) -> bool:
        """Return True after several consecutive frames exceed the threshold."""
        scores = self.predict_frame(frame)
        hit = any(score >= self.threshold for score in scores.values())
        if hit:
            self._hit_streak += 1
        else:
            self._hit_streak = 0
        if self._hit_streak < self._required_hits:
            return False
        best = max(scores.items(), key=lambda item: item[1], default=("", 0.0))
        _logger.info(
            "Streaming wake-word triggered by %r (score: %.3f, hits=%d)",
            best[0],
            best[1],
            self._hit_streak,
        )
        self._hit_streak = 0
        return True

    def reset(self) -> None:
        """Reset internal frame buffers of openwakeword model."""
        self._hit_streak = 0
        if self._model is not None:
            try:
                self._model.reset()
            except Exception:
                pass
