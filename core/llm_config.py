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

DEFAULT_INTENT_CONFIDENCE = 0.7


def models_for_intent(
    *,
    backend: str = "",
    intent_provider_id: str = "",
    selected_model: str = "",
) -> List[str]:
    """No preset Intent catalog — only the model the user already saved (if any).

    Live model lists come from ``fetch_remote_models`` after the user pastes a key.
    ``backend`` / ``intent_provider_id`` are kept for call-site compatibility.
    """
    del backend, intent_provider_id
    selected = (selected_model or "").strip()
    return [selected] if selected else []


def default_intent_model_for(
    *,
    backend: str = "",
    intent_provider_id: str = "",
    main_model: str = "",
) -> str:
    """Prefer the user's main chat model; never invent a preset Intent model id."""
    del backend, intent_provider_id
    return (main_model or "").strip()


def intent_fetch_base_url(
    *,
    backend: str,
    intent_provider_id: str,
    intent_base_url: str = "",
) -> str:
    """Resolve the OpenAI-compatible base URL used to list Intent models."""
    explicit = (intent_base_url or "").strip().rstrip("/")
    if explicit:
        return explicit
    backend_norm = (backend or "gemini").strip().lower()
    if backend_norm == "gemini":
        preset = preset_by_id("gemini")
    else:
        preset = preset_by_id((intent_provider_id or "").strip())
    return (preset.base_url if preset else "").strip().rstrip("/")


@dataclass
class ProviderPreset:
    id: str
    label: str
    base_url: str
    models: List[str] = field(default_factory=list)
    api_key_placeholder: str = "API key"
    default_api_key: str = ""
    allow_empty_key: bool = False


# Presets only carry endpoint metadata — model IDs are fetched live after the user pastes a key.
PROVIDER_PRESETS: List[ProviderPreset] = [
    ProviderPreset(
        id="openai",
        label="ChatGPT",
        base_url="https://api.openai.com/v1",
        api_key_placeholder="sk-...",
    ),
    ProviderPreset(
        id="gemini",
        label="Gemini",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        api_key_placeholder="AIza...",
    ),
    ProviderPreset(
        id="openrouter",
        label="OpenRouter",
        base_url=DEFAULT_OPENROUTER_URL,
        api_key_placeholder="sk-or-v1-...",
    ),
    ProviderPreset(
        id="groq",
        label="Groq",
        base_url="https://api.groq.com/openai/v1",
        api_key_placeholder="gsk_...",
    ),
    ProviderPreset(
        id="deepseek",
        label="DeepSeek",
        base_url="https://api.deepseek.com/v1",
        api_key_placeholder="sk-...",
    ),
    ProviderPreset(
        id="together",
        label="Together AI",
        base_url="https://api.together.xyz/v1",
        api_key_placeholder="together-...",
    ),
    ProviderPreset(
        id="ollama",
        label="Ollama (local)",
        base_url="http://localhost:11434/v1",
        api_key_placeholder="ollama (optional)",
        default_api_key="ollama",
        allow_empty_key=True,
    ),
    ProviderPreset(
        id="lmstudio",
        label="LM Studio (local)",
        base_url="http://localhost:1234/v1",
        api_key_placeholder="lm-studio (optional)",
        default_api_key="lm-studio",
        allow_empty_key=True,
    ),
    ProviderPreset(
        id="custom",
        label="Custom / Other",
        base_url="",
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
    intent_model: str = ""
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


def connection_to_dict(connection: LlmConnection) -> Dict[str, Any]:
    """Serialize a connection for local ``user_settings.json`` (not ``.env``)."""
    return {
        "provider_id": connection.provider_id,
        "label": connection.label,
        "base_url": connection.base_url.rstrip("/"),
        "api_key": connection.api_key,
        "model": connection.model,
        "gemini_api_key": connection.gemini_api_key,
        "intent_enabled": bool(connection.intent_enabled),
        "intent_backend": connection.intent_backend or "gemini",
        "intent_provider_id": connection.intent_provider_id or "openrouter",
        "intent_base_url": (connection.intent_base_url or "").rstrip("/"),
        "intent_api_key": connection.intent_api_key,
        "intent_model": connection.intent_model,
        "intent_confidence": float(connection.intent_confidence),
    }


def connection_from_dict(data: Mapping[str, Any]) -> LlmConnection:
    """Deserialize a connection from local settings."""
    provider_id = str(data.get("provider_id") or "openrouter").strip() or "openrouter"
    preset = preset_by_id(provider_id)
    intent_backend = str(data.get("intent_backend") or "gemini").strip().lower()
    if intent_backend not in {"gemini", "openai"}:
        intent_backend = "gemini"
    try:
        intent_confidence = float(
            data.get("intent_confidence", DEFAULT_INTENT_CONFIDENCE)
        )
    except (TypeError, ValueError):
        intent_confidence = DEFAULT_INTENT_CONFIDENCE
    return LlmConnection(
        provider_id=provider_id,
        label=str(data.get("label") or (preset.label if preset else "Custom")),
        base_url=str(data.get("base_url") or (preset.base_url if preset else DEFAULT_OPENROUTER_URL))
        .strip()
        .rstrip("/"),
        api_key=str(data.get("api_key") or ""),
        model=str(data.get("model") or ""),
        gemini_api_key=str(data.get("gemini_api_key") or ""),
        intent_enabled=bool(data.get("intent_enabled", True)),
        intent_backend=intent_backend,
        intent_provider_id=str(data.get("intent_provider_id") or provider_id or "openrouter"),
        intent_base_url=str(data.get("intent_base_url") or "").strip().rstrip("/"),
        intent_api_key=str(data.get("intent_api_key") or ""),
        intent_model=str(data.get("intent_model") or ""),
        intent_confidence=max(0.0, min(1.0, intent_confidence)),
    )


def load_saved_connection() -> Optional[LlmConnection]:
    """Load LLM settings from local ``user_settings.json`` when present."""
    from core.user_settings import load_user_settings

    data = load_user_settings()
    llm = data.get("llm")
    if isinstance(llm, dict) and llm:
        return connection_from_dict(llm)
    return None


def save_connection(connection: LlmConnection) -> Path:
    """Persist LLM/Intent settings locally — never writes secrets into ``.env``."""
    from core.user_settings import save_user_settings

    return save_user_settings({"llm": connection_to_dict(connection)})


def connection_from_env() -> LlmConnection:
    """Active connection: local ``user_settings.json`` first, else process env / ``.env``.

    UI saves go to the local file so open-source checkouts are not littered with keys.
    Optional ``.env`` remains for bootstrap, CI, and headless runs.
    """
    saved = load_saved_connection()
    if saved is not None:
        return saved
    return _connection_from_environ()


def _connection_from_environ() -> LlmConnection:
    """Build a connection from environment / optional ``.env`` values only."""
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
    model = (os.getenv("MODEL_NAME") or os.getenv("LLM_MODEL") or "").strip()
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
    # Default Intent to the same provider stack the user chose for chat.
    intent_provider_id = (
        os.getenv("INTENT_PROVIDER") or provider_id or "openrouter"
    ).strip() or "openrouter"
    if not intent_base_url and intent_backend == "openai":
        intent_base_url = base_url
    if not intent_api_key and intent_backend == "openai":
        intent_api_key = api_key
    default_intent_model = default_intent_model_for(
        backend=intent_backend,
        intent_provider_id=intent_provider_id,
        main_model=model,
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
    """Map a connection to process-env keys (in-memory / optional bootstrap only)."""
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
        "INTENT_MODEL": connection.intent_model
        or default_intent_model_for(
            backend=connection.intent_backend or "gemini",
            intent_provider_id=connection.intent_provider_id or connection.provider_id,
            main_model=connection.model,
        ),
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
