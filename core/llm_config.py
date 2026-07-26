"""Dynamic OpenAI-compatible LLM provider configuration."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

_ROOT = Path(__file__).resolve().parent.parent
PROVIDERS_PATH = _ROOT / "llm_providers.json"

DEFAULT_OPENROUTER_URL = "https://openrouter.ai/api/v1"

INTENT_MODEL_CHOICES = [
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-1.5-flash",
    "gemini-1.5-pro",
]
DEFAULT_INTENT_MODEL = "gemini-2.0-flash"
DEFAULT_INTENT_CONFIDENCE = 0.7


@dataclass
class ProviderPreset:
    id: str
    label: str
    base_url: str
    models: List[str] = field(default_factory=list)
    api_key_placeholder: str = "API key"
    default_api_key: str = ""
    allow_empty_key: bool = False


PROVIDER_PRESETS: List[ProviderPreset] = [
    ProviderPreset(
        id="openai",
        label="ChatGPT",
        base_url="https://api.openai.com/v1",
        models=["gpt-4o-mini", "gpt-4o", "gpt-4.1-mini", "gpt-4.1", "o4-mini"],
        api_key_placeholder="sk-...",
    ),
    ProviderPreset(
        id="gemini",
        label="Gemini",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        models=[
            "gemini-2.0-flash",
            "gemini-2.0-flash-lite",
            "gemini-2.5-flash",
            "gemini-2.5-flash-lite",
            "gemini-1.5-flash",
            "gemini-1.5-pro",
        ],
        api_key_placeholder="AIza...",
    ),
    ProviderPreset(
        id="openrouter",
        label="OpenRouter",
        base_url=DEFAULT_OPENROUTER_URL,
        models=[
            "openrouter/free",
            "openrouter/owl-alpha",
            "openai/gpt-oss-20b:free",
            "google/gemma-4-31b-it:free",
            "google/gemma-4-26b-a4b-it:free",
            "meta-llama/llama-3.3-70b-instruct:free",
            "qwen/qwen3-coder",
            "openai/gpt-oss-120b",
        ],
        api_key_placeholder="sk-or-v1-...",
    ),
    ProviderPreset(
        id="groq",
        label="Groq",
        base_url="https://api.groq.com/openai/v1",
        models=[
            "llama-3.3-70b-versatile",
            "llama-3.1-8b-instant",
            "openai/gpt-oss-20b",
        ],
        api_key_placeholder="gsk_...",
    ),
    ProviderPreset(
        id="deepseek",
        label="DeepSeek",
        base_url="https://api.deepseek.com/v1",
        models=["deepseek-chat", "deepseek-reasoner"],
        api_key_placeholder="sk-...",
    ),
    ProviderPreset(
        id="together",
        label="Together AI",
        base_url="https://api.together.xyz/v1",
        models=[
            "meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo",
            "Qwen/Qwen2.5-72B-Instruct-Turbo",
        ],
        api_key_placeholder="together-...",
    ),
    ProviderPreset(
        id="ollama",
        label="Ollama (local)",
        base_url="http://localhost:11434/v1",
        models=["llama3.2", "qwen2.5", "mistral", "phi4"],
        api_key_placeholder="ollama (optional)",
        default_api_key="ollama",
        allow_empty_key=True,
    ),
    ProviderPreset(
        id="lmstudio",
        label="LM Studio (local)",
        base_url="http://localhost:1234/v1",
        models=["local-model"],
        api_key_placeholder="lm-studio (optional)",
        default_api_key="lm-studio",
        allow_empty_key=True,
    ),
    ProviderPreset(
        id="custom",
        label="Custom / Other",
        base_url="",
        models=[],
        api_key_placeholder="API key (if required)",
        allow_empty_key=True,
    ),
]


def is_free_model(model_id: str) -> bool:
    """Heuristic for free-tier / :free tagged model IDs."""
    mid = (model_id or "").strip().lower()
    if not mid:
        return False
    return (
        mid.endswith(":free")
        or mid.endswith("/free")
        or ":free" in mid
        or "/free" in mid
        or mid in {"openrouter/free", "free"}
    )


@dataclass
class LlmConnection:
    """Active LLM endpoint + intent classifier configuration."""

    provider_id: str = "openrouter"
    label: str = "OpenRouter"
    base_url: str = DEFAULT_OPENROUTER_URL
    api_key: str = ""
    model: str = "openrouter/free"
    gemini_api_key: str = ""
    intent_enabled: bool = True
    intent_backend: str = "gemini"  # gemini | openai
    intent_provider_id: str = "openrouter"
    intent_base_url: str = ""
    intent_api_key: str = ""
    intent_model: str = DEFAULT_INTENT_MODEL
    intent_confidence: float = DEFAULT_INTENT_CONFIDENCE


def preset_by_id(provider_id: str) -> Optional[ProviderPreset]:
    for preset in PROVIDER_PRESETS:
        if preset.id == provider_id:
            return preset
    return None


def load_saved_providers() -> List[Dict[str, Any]]:
    if not PROVIDERS_PATH.exists():
        return []
    try:
        data = json.loads(PROVIDERS_PATH.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
    except (OSError, json.JSONDecodeError):
        return []
    return []


def save_custom_provider(provider: Mapping[str, Any]) -> None:
    """Append or update a custom provider entry in llm_providers.json."""
    providers = load_saved_providers()
    label = str(provider.get("label") or "Custom").strip() or "Custom"
    base_url = str(provider.get("base_url") or "").strip()
    model = str(provider.get("model") or "").strip()
    entry = {
        "id": str(provider.get("id") or f"custom_{abs(hash((label, base_url))) % 10_000_000}"),
        "label": label,
        "base_url": base_url,
        "model": model,
        "api_key": str(provider.get("api_key") or ""),
    }
    replaced = False
    for idx, existing in enumerate(providers):
        if existing.get("id") == entry["id"] or (
            existing.get("label") == entry["label"] and existing.get("base_url") == entry["base_url"]
        ):
            providers[idx] = entry
            replaced = True
            break
    if not replaced:
        providers.append(entry)
    PROVIDERS_PATH.write_text(json.dumps(providers, indent=2), encoding="utf-8")


def connection_from_env() -> LlmConnection:
    """Build the active connection from environment / .env values."""
    provider_id = (os.getenv("LLM_PROVIDER") or "openrouter").strip() or "openrouter"
    preset = preset_by_id(provider_id) or preset_by_id("openrouter")
    assert preset is not None

    base_url = (
        os.getenv("LLM_BASE_URL")
        or os.getenv("OPENAI_BASE_URL")
        or preset.base_url
        or DEFAULT_OPENROUTER_URL
    ).strip()
    api_key = (
        os.getenv("LLM_API_KEY")
        or os.getenv("OPENROUTER_API_KEY")
        or os.getenv("OPENAI_API_KEY")
        or preset.default_api_key
        or ""
    ).strip()
    model = (
        os.getenv("MODEL_NAME")
        or os.getenv("LLM_MODEL")
        or (preset.models[0] if preset.models else "gpt-4o-mini")
    ).strip()
    gemini = (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip()
    intent_backend = (os.getenv("INTENT_BACKEND") or "gemini").strip().lower()
    if intent_backend not in {"gemini", "openai"}:
        intent_backend = "gemini"
    intent_enabled_raw = (os.getenv("INTENT_ENABLED") or "true").strip().lower()
    intent_enabled = intent_enabled_raw in {"1", "true", "yes", "on"}
    intent_api_key = (
        os.getenv("INTENT_API_KEY") or gemini or ""
    ).strip()
    intent_base_url = (os.getenv("INTENT_BASE_URL") or "").strip()
    intent_provider_id = (os.getenv("INTENT_PROVIDER") or "openrouter").strip() or "openrouter"
    default_intent_model = (
        DEFAULT_INTENT_MODEL if intent_backend == "gemini" else "openrouter/free"
    )
    intent_model = (os.getenv("INTENT_MODEL") or default_intent_model).strip()
    try:
        intent_confidence = float(
            os.getenv("INTENT_CONFIDENCE_THRESHOLD") or DEFAULT_INTENT_CONFIDENCE
        )
    except ValueError:
        intent_confidence = DEFAULT_INTENT_CONFIDENCE
    intent_confidence = max(0.0, min(1.0, intent_confidence))

    return LlmConnection(
        provider_id=provider_id,
        label=preset.label,
        base_url=base_url.rstrip("/"),
        api_key=api_key,
        model=model,
        gemini_api_key=gemini or intent_api_key,
        intent_enabled=intent_enabled,
        intent_backend=intent_backend,
        intent_provider_id=intent_provider_id,
        intent_base_url=intent_base_url.rstrip("/"),
        intent_api_key=intent_api_key,
        intent_model=intent_model or default_intent_model,
        intent_confidence=intent_confidence,
    )


def connection_to_env_updates(connection: LlmConnection) -> Dict[str, str]:
    """Map a connection to .env keys."""
    intent_key = connection.intent_api_key or connection.gemini_api_key
    updates = {
        "LLM_PROVIDER": connection.provider_id,
        "LLM_BASE_URL": connection.base_url.rstrip("/"),
        "LLM_API_KEY": connection.api_key,
        "MODEL_NAME": connection.model,
        "INTENT_ENABLED": "true" if connection.intent_enabled else "false",
        "INTENT_BACKEND": connection.intent_backend or "gemini",
        "INTENT_PROVIDER": connection.intent_provider_id or "openrouter",
        "INTENT_BASE_URL": (connection.intent_base_url or "").rstrip("/"),
        "INTENT_API_KEY": intent_key,
        "INTENT_MODEL": connection.intent_model or DEFAULT_INTENT_MODEL,
        "INTENT_CONFIDENCE_THRESHOLD": f"{connection.intent_confidence:.2f}",
        "GEMINI_API_KEY": intent_key if (connection.intent_backend or "gemini") == "gemini" else (
            connection.gemini_api_key or intent_key
        ),
    }
    # Keep legacy OpenRouter key in sync when using OpenRouter.
    if "openrouter.ai" in connection.base_url:
        updates["OPENROUTER_API_KEY"] = connection.api_key
    return updates


def fetch_remote_models(base_url: str, api_key: str, timeout: float = 8.0) -> List[str]:
    """List model IDs from an OpenAI-compatible ``/models`` endpoint."""
    from openai import OpenAI

    url = (base_url or "").strip().rstrip("/")
    if not url:
        raise ValueError("Base URL is required to fetch models.")

    client = OpenAI(api_key=api_key or "not-needed", base_url=url, timeout=timeout)
    response = client.models.list()
    ids: List[str] = []
    for item in getattr(response, "data", []) or []:
        model_id = getattr(item, "id", None)
        if model_id:
            ids.append(str(model_id))
    ids.sort()
    return ids


def test_llm_connection(
    base_url: str,
    api_key: str,
    model: str,
    timeout: float = 12.0,
) -> str:
    """Send a tiny completion to verify the endpoint works. Returns reply text."""
    from openai import OpenAI

    url = (base_url or "").strip().rstrip("/")
    if not url:
        raise ValueError("Base URL is required.")
    if not model.strip():
        raise ValueError("Model name is required.")

    client = OpenAI(api_key=api_key or "not-needed", base_url=url, timeout=timeout)
    response = client.chat.completions.create(
        model=model.strip(),
        messages=[
            {"role": "system", "content": "Reply with exactly: ok"},
            {"role": "user", "content": "ping"},
        ],
        max_tokens=8,
    )
    content = ""
    if response.choices:
        content = (response.choices[0].message.content or "").strip()
    return content or "ok"
