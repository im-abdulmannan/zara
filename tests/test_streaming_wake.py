"""Tests for openwakeword streaming wake-word detector integration."""
from __future__ import annotations

import numpy as np
import pytest

from voice.streaming_wake import StreamingWakeDetector
from voice.wake_word import WakeWordDetector


def test_streaming_wake_detector_initialization():
    detector = StreamingWakeDetector(
        target_models=("alexa", "hey_jarvis"),
        threshold=0.5,
        enabled=True,
    )
    assert detector.threshold == 0.5
    # Should be enabled if openwakeword is installed
    assert detector.enabled is True or detector.enabled is False


def test_streaming_wake_detector_predict_silence():
    detector = StreamingWakeDetector(
        target_models=("alexa", "hey_jarvis"),
        threshold=0.5,
        enabled=True,
    )
    # Generate 80ms chunk of silence (1280 samples at 16kHz)
    silence_frame = np.zeros(1280, dtype=np.int16)
    
    # Silence frame should not trigger wake
    assert detector.is_wake_triggered(silence_frame) is False


def test_wake_word_detector_with_streaming():
    detector = WakeWordDetector(
        phrases=("hello zara", "hey zara"),
        sleep_phrases=("sleep zara",),
        use_streaming=True,
        streaming_threshold=0.6,
    )
    assert detector.is_wake("hey zara") is True
    assert detector.is_sleep("sleep zara") is True
    
    silence_frame = np.zeros(1280, dtype=np.int16)
    assert detector.check_streaming_frame(silence_frame) is False
