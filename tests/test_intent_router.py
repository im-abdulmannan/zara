"""Tests for intent routing (no Gemini API calls)."""
from __future__ import annotations

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
        intent=Intent.OPEN_APPLICATION,
        confidence=0.1,
        entities={"app": "chrome"},
    )
    assert router.route("open chrome", result) is None


def test_router_reload_updates_confidence_threshold(router):
    from intent.config import IntentConfig

    result = ClassificationResult(
        intent=Intent.OPEN_APPLICATION,
        confidence=0.6,
        entities={"app": "chrome"},
    )
    assert router.route("open chrome", result) is not None

    router.reload_settings(
        IntentConfig(api_key="test", confidence_threshold=0.9, enabled=True)
    )
    assert router.route("open chrome", result) is None


def test_router_disabled_defers_to_llm(router):
    from intent.config import IntentConfig

    router.reload_settings(
        IntentConfig(api_key="test", confidence_threshold=0.5, enabled=False)
    )
    result = ClassificationResult(
        intent=Intent.OPEN_APPLICATION,
        confidence=0.95,
        entities={"app": "chrome"},
    )
    assert router.route("open chrome", result) is None


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
