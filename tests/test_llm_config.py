"""Tests for dynamic LLM provider configuration."""
from __future__ import annotations

from core.llm_config import (
    LlmConnection,
    connection_to_env_updates,
    preset_by_id,
    save_custom_provider,
    load_saved_providers,
)


def test_openrouter_preset_exists():
    preset = preset_by_id("openrouter")
    assert preset is not None
    assert "openrouter.ai" in preset.base_url
    assert preset.models


def test_connection_to_env_updates_syncs_openrouter_key():
    conn = LlmConnection(
        provider_id="openrouter",
        label="OpenRouter",
        base_url="https://openrouter.ai/api/v1",
        api_key="sk-test",
        model="openrouter/free",
        gemini_api_key="gem-test",
        intent_enabled=True,
        intent_backend="gemini",
        intent_api_key="gem-test",
        intent_model="gemini-2.0-flash",
        intent_confidence=0.85,
    )
    updates = connection_to_env_updates(conn)
    assert updates["LLM_BASE_URL"] == "https://openrouter.ai/api/v1"
    assert updates["LLM_API_KEY"] == "sk-test"
    assert updates["OPENROUTER_API_KEY"] == "sk-test"
    assert updates["MODEL_NAME"] == "openrouter/free"
    assert updates["INTENT_ENABLED"] == "true"
    assert updates["INTENT_BACKEND"] == "gemini"
    assert updates["INTENT_MODEL"] == "gemini-2.0-flash"
    assert updates["INTENT_CONFIDENCE_THRESHOLD"] == "0.85"
    assert updates["GEMINI_API_KEY"] == "gem-test"


def test_intent_openai_backend_env_mapping():
    conn = LlmConnection(
        provider_id="openrouter",
        label="OpenRouter",
        base_url="https://openrouter.ai/api/v1",
        api_key="sk-main",
        model="openrouter/free",
        intent_enabled=True,
        intent_backend="openai",
        intent_provider_id="groq",
        intent_base_url="https://api.groq.com/openai/v1",
        intent_api_key="gsk-test",
        intent_model="llama-3.3-70b-versatile",
        intent_confidence=0.6,
    )
    updates = connection_to_env_updates(conn)
    assert updates["INTENT_BACKEND"] == "openai"
    assert updates["INTENT_BASE_URL"] == "https://api.groq.com/openai/v1"
    assert updates["INTENT_API_KEY"] == "gsk-test"
    assert updates["INTENT_MODEL"] == "llama-3.3-70b-versatile"


def test_custom_provider_persistence(tmp_path, monkeypatch):
    import core.llm_config as llm_config

    path = tmp_path / "llm_providers.json"
    monkeypatch.setattr(llm_config, "PROVIDERS_PATH", path)
    save_custom_provider(
        {
            "label": "My Proxy",
            "base_url": "http://127.0.0.1:8080/v1",
            "model": "my-model",
            "api_key": "abc",
        }
    )
    saved = load_saved_providers()
    assert len(saved) == 1
    assert saved[0]["label"] == "My Proxy"
    assert saved[0]["base_url"] == "http://127.0.0.1:8080/v1"
