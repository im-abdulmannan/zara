"""Tests for intent model helpers."""
from __future__ import annotations

from intent.models import ClassificationResult, Intent


def test_intent_from_value_string():
    assert Intent.from_value("REMINDER_CREATE") is Intent.REMINDER_CREATE


def test_intent_from_value_unknown_defaults_to_chat():
    assert Intent.from_value("NOT_A_REAL_INTENT") is Intent.CHAT


def test_classification_result_to_dict():
    result = ClassificationResult(
        intent=Intent.NOTE_CREATE,
        confidence=0.88,
        entities={"title": "x"},
    )
    data = result.to_dict()
    assert data["intent"] == "NOTE_CREATE"
    assert data["confidence"] == 0.88
    assert data["entities"]["title"] == "x"


def test_chat_fallback():
    result = ClassificationResult.chat_fallback(confidence=0.0)
    assert result.intent is Intent.CHAT
