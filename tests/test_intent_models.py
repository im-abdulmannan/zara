"""Tests for intent model helpers."""
from __future__ import annotations

from intent.models import ClassificationResult, Intent


def test_intent_from_value_string():
    assert Intent.from_value("OPEN_APPLICATION") is Intent.OPEN_APPLICATION


def test_intent_from_value_unknown_defaults_to_chat():
    assert Intent.from_value("NOT_A_REAL_INTENT") is Intent.CHAT


def test_classification_result_to_dict():
    result = ClassificationResult(
        intent=Intent.WEB_SEARCH,
        confidence=0.88,
        entities={"query": "python"},
    )
    data = result.to_dict()
    assert data["intent"] == "WEB_SEARCH"
    assert data["confidence"] == 0.88
    assert data["entities"]["query"] == "python"


def test_chat_fallback():
    result = ClassificationResult.chat_fallback(confidence=0.0)
    assert result.intent is Intent.CHAT
