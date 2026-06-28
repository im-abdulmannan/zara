"""Tests for wake-word and sleep-phrase detection."""
from __future__ import annotations

import pytest

from voice.wake_word import WakeWordDetector


@pytest.fixture
def detector():
    return WakeWordDetector(
        phrases=("hello zara", "hey zara", "zara"),
        sleep_phrases=("sleep zara", "go to sleep"),
    )


@pytest.mark.parametrize(
    "text",
    [
        "hey zara",
        "Hey Zara, are you there?",
        "hello zara",
        "zara",
    ],
)
def test_wake_phrases_detected(detector, text):
    assert detector.is_wake(text) is True


@pytest.mark.parametrize(
    "text",
    [
        "hello world",
        "open chrome",
        "",
        "   ",
    ],
)
def test_non_wake_phrases_rejected(detector, text):
    assert detector.is_wake(text) is False


@pytest.mark.parametrize(
    "text",
    [
        "sleep zara",
        "go to sleep",
        "Okay, go to sleep now",
    ],
)
def test_sleep_phrases_detected(detector, text):
    assert detector.is_sleep(text) is True


def test_sleep_not_wake(detector):
    """Sleep phrases without the wake substring should not trigger wake."""
    assert detector.is_sleep("go to sleep") is True
    assert detector.is_wake("go to sleep") is False


def test_sleep_phrase_containing_wake_word_also_matches_wake(detector):
    """'sleep zara' contains 'zara' — both sleep and wake match (known quirk)."""
    assert detector.is_sleep("sleep zara") is True
    assert detector.is_wake("sleep zara") is True
