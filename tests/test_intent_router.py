"""Tests for intent routing (no Gemini API calls)."""
from __future__ import annotations

from datetime import datetime

import pytest

from intent.models import ClassificationResult, Intent
from router.intent_router import IntentRouter


@pytest.fixture
def router():
    from intent.config import IntentConfig

    config = IntentConfig(
        api_key="test",
        confidence_threshold=0.5,
    )
    return IntentRouter(config=config)


def test_chat_intent_defers_to_llm(router):
    result = ClassificationResult(intent=Intent.CHAT, confidence=1.0)
    assert router.route("hello", result) is None


def test_low_confidence_defers_to_llm(router):
    result = ClassificationResult(
        intent=Intent.REMINDER_CREATE,
        confidence=0.1,
        entities={"title": "call mom", "time": "5pm"},
    )
    assert router.route("remind me at 5pm to call mom", result) is None


def test_reminder_create_routes_to_set_reminder(router):
    result = ClassificationResult(
        intent=Intent.REMINDER_CREATE,
        confidence=0.95,
        entities={"title": "call mom", "time": "10:00"},
    )
    payload = router.route("remind me at 10:00 to call mom", result)
    assert payload is not None
    assert payload["tool"] == "set_reminder"
    assert payload["title"] == "call mom"
    assert "datetime" in payload


def test_meeting_query_routes_to_calendar(router):
    result = ClassificationResult(
        intent=Intent.MEETING_QUERY,
        confidence=0.9,
        entities={},
    )
    payload = router.route("what meetings do I have today?", result)
    assert payload["tool"] == "query_calendar"


def test_open_application_routes_to_open_app(router):
    result = ClassificationResult(
        intent=Intent.OPEN_APPLICATION,
        confidence=0.9,
        entities={"app": "chrome"},
    )
    payload = router.route("open chrome", result)
    assert payload["tool"] == "open_app"
    assert payload["app"] == "chrome"


def test_web_search_routes_to_google(router):
    result = ClassificationResult(
        intent=Intent.WEB_SEARCH,
        confidence=0.9,
        entities={"query": "python tutorials"},
    )
    payload = router.route("search for python tutorials", result)
    assert payload["tool"] == "search_google"


def test_system_command_shutdown(router):
    result = ClassificationResult(
        intent=Intent.SYSTEM_COMMAND,
        confidence=0.9,
        entities={"command": "shutdown"},
    )
    payload = router.route("shut down the computer", result)
    assert payload["tool"] == "shutdown_pc"


def test_memory_save_routes_to_remember(router):
    result = ClassificationResult(
        intent=Intent.MEMORY_SAVE,
        confidence=0.9,
        entities={"kind": "fact", "value": "I like tea"},
    )
    payload = router.route("remember that I like tea", result)
    assert payload["tool"] == "remember"
    assert payload["value"] == "I like tea"


def test_habit_create_routes_correctly(router):
    result = ClassificationResult(
        intent=Intent.HABIT_CREATE,
        confidence=0.9,
        entities={"title": "drink water", "frequency": "daily", "time": "07:00"},
    )
    payload = router.route("track drinking water daily at 7am", result)
    assert payload["tool"] == "create_habit"
    assert payload["title"] == "drink water"
