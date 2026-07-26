"""Tests for wake-word and sleep-phrase detection."""
from __future__ import annotations

import pytest

from voice.wake_word import WakeWordDetector


@pytest.fixture
def detector():
    return WakeWordDetector(
        phrases=("hello zara", "hey zara", "zara"),
        sleep_phrases=("sleep zara", "go to sleep", "goodbye zara"),
        use_streaming=False,
    )


@pytest.mark.parametrize(
    "text",
    [
        "hey zara",
        "Hey Zara, are you there?",
        "hello zara",
        "zara",
        "Zara what's the time",
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
        "is zara ready",  # bare name not mid-sentence
        "czara",
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
        "goodbye zara",
    ],
)
def test_sleep_phrases_detected(detector, text):
    assert detector.is_sleep(text) is True


def test_sleep_not_wake(detector):
    """Sleep phrases should never also count as wake."""
    assert detector.is_sleep("go to sleep") is True
    assert detector.is_wake("go to sleep") is False


def test_sleep_phrase_containing_name_is_not_wake(detector):
    """'sleep zara' must sleep, not wake, even though it contains 'zara'."""
    assert detector.is_sleep("sleep zara") is True
    assert detector.is_wake("sleep zara") is False


def test_extract_command_after_wake(detector):
    assert detector.extract_command_after_wake("hey zara, how are you?") == "how are you"
    assert detector.extract_command_after_wake("hey zara") == ""


@pytest.mark.parametrize(
    "text",
    [
        "aizara, how are you?",
        "aizara how are you aizara how are you",
        "heyzara",
        "hey zaara",
    ],
)
def test_wake_tolerates_whisper_mishearings(detector, text):
    assert detector.is_wake(text) is True


def test_extract_command_from_misheard_wake(detector):
    assert detector.extract_command_after_wake("aizara, how are you?") == "how are you"
