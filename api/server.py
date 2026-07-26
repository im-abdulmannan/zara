"""FastAPI app serving the React UI and settings endpoints."""
from __future__ import annotations

import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from agent import apply_llm_connection, get_active_connection_summary
from api.status_store import get_status, update_status
from core.llm_config import (
    INTENT_MODEL_CHOICES,
    LlmConnection,
    PROVIDER_PRESETS,
    connection_from_env,
    connection_to_env_updates,
    fetch_remote_models,
    is_free_model,
    load_saved_providers,
    preset_by_id,
    test_llm_connection,
)
from memory.store import get_name, get_preferences, remember_name, set_preference
from ui.env_settings import upsert_env_values

_ROOT = Path(__file__).resolve().parent.parent
_WEB_DIST = _ROOT / "web" / "dist"

app = FastAPI(title="Zara UI API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ProviderSaveBody(BaseModel):
    provider_id: str
    base_url: str
    api_key: str = ""
    model: str


class IntentSaveBody(BaseModel):
    intent_enabled: bool = True
    intent_backend: str = "gemini"
    intent_provider_id: str = "openrouter"
    intent_base_url: str = ""
    intent_api_key: str = ""
    intent_model: str = ""
    intent_confidence: float = Field(default=0.7, ge=0.0, le=1.0)
    # False when only toggling enable/disable from the gate.
    validate_details: bool = True


class FetchModelsBody(BaseModel):
    base_url: str
    api_key: str = ""


class TestConnectionBody(BaseModel):
    base_url: str
    api_key: str = ""
    model: str


class ProfileBody(BaseModel):
    name: str = ""
    browser: str = ""
    notes: str = ""


def _connection_dict(connection: LlmConnection) -> Dict[str, Any]:
    return {
        "provider_id": connection.provider_id,
        "label": connection.label,
        "base_url": connection.base_url,
        "api_key": connection.api_key,
        "model": connection.model,
        "intent_enabled": connection.intent_enabled,
        "intent_backend": connection.intent_backend,
        "intent_provider_id": connection.intent_provider_id,
        "intent_base_url": connection.intent_base_url,
        "intent_api_key": connection.intent_api_key or connection.gemini_api_key,
        "intent_model": connection.intent_model,
        "intent_confidence": connection.intent_confidence,
        "active_summary": get_active_connection_summary(),
    }


@app.get("/api/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/api/status")
def live_status() -> Dict[str, Any]:
    status = get_status()
    status["active_model"] = status.get("active_model") or get_active_connection_summary()
    return status


@app.get("/api/providers")
def list_providers() -> Dict[str, Any]:
    presets = [
        {
            "id": p.id,
            "label": p.label,
            "base_url": p.base_url,
            "models": p.models,
            "api_key_placeholder": p.api_key_placeholder,
            "allow_empty_key": p.allow_empty_key,
            "default_api_key": p.default_api_key,
        }
        for p in PROVIDER_PRESETS
    ]
    saved = load_saved_providers()
    return {
        "presets": presets,
        "saved": saved,
        "intent_models": list(INTENT_MODEL_CHOICES),
    }


@app.get("/api/connection")
def get_connection() -> Dict[str, Any]:
    return _connection_dict(connection_from_env())


@app.put("/api/provider")
def save_provider(body: ProviderSaveBody) -> Dict[str, Any]:
    existing = connection_from_env()
    preset = preset_by_id(body.provider_id)
    if not body.base_url.strip():
        raise HTTPException(status_code=400, detail="Base URL is required.")
    if not body.model.strip():
        raise HTTPException(status_code=400, detail="Model is required.")
    allow_empty = bool(preset and preset.allow_empty_key)
    if not body.api_key.strip() and not allow_empty:
        raise HTTPException(status_code=400, detail="API key is required.")

    connection = LlmConnection(
        provider_id=body.provider_id,
        label=preset.label if preset else "Custom",
        base_url=body.base_url.strip().rstrip("/"),
        api_key=body.api_key.strip(),
        model=body.model.strip(),
        gemini_api_key=existing.gemini_api_key,
        intent_enabled=existing.intent_enabled,
        intent_backend=existing.intent_backend,
        intent_provider_id=existing.intent_provider_id,
        intent_base_url=existing.intent_base_url,
        intent_api_key=existing.intent_api_key,
        intent_model=existing.intent_model,
        intent_confidence=existing.intent_confidence,
    )
    upsert_env_values(connection_to_env_updates(connection))
    apply_llm_connection(connection)
    update_status(active_model=get_active_connection_summary())
    return _connection_dict(connection)


@app.put("/api/intent")
def save_intent(body: IntentSaveBody) -> Dict[str, Any]:
    existing = connection_from_env()
    backend = (body.intent_backend or "gemini").lower()
    if backend not in {"gemini", "openai"}:
        backend = "gemini"

    if body.intent_enabled and body.validate_details:
        if not body.intent_model.strip():
            raise HTTPException(status_code=400, detail="Intent model is required.")
        if backend == "openai" and not body.intent_base_url.strip():
            raise HTTPException(status_code=400, detail="Intent Base URL is required.")
        if backend == "gemini" and not body.intent_api_key.strip():
            raise HTTPException(status_code=400, detail="Gemini API key is required.")
        if backend == "openai" and not body.intent_api_key.strip():
            preset = preset_by_id(body.intent_provider_id)
            allow_empty = bool(preset and preset.allow_empty_key) or (
                "localhost" in body.intent_base_url
            )
            if not allow_empty:
                raise HTTPException(status_code=400, detail="Intent API key is required.")

    connection = LlmConnection(
        provider_id=existing.provider_id,
        label=existing.label,
        base_url=existing.base_url,
        api_key=existing.api_key,
        model=existing.model,
        gemini_api_key=body.intent_api_key if backend == "gemini" else existing.gemini_api_key,
        intent_enabled=bool(body.intent_enabled),
        intent_backend=backend,
        intent_provider_id=body.intent_provider_id or "openrouter",
        intent_base_url=body.intent_base_url.strip().rstrip("/"),
        intent_api_key=body.intent_api_key.strip(),
        intent_model=body.intent_model.strip(),
        intent_confidence=float(body.intent_confidence),
    )
    upsert_env_values(connection_to_env_updates(connection))
    apply_llm_connection(connection)
    update_status(active_model=get_active_connection_summary())
    return _connection_dict(connection)


@app.post("/api/models/fetch")
def models_fetch(body: FetchModelsBody) -> Dict[str, List[Any]]:
    try:
        models = fetch_remote_models(body.base_url, body.api_key)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "models": models,
        "free": [m for m in models if is_free_model(m)],
    }


@app.post("/api/connection/test")
def connection_test(body: TestConnectionBody) -> Dict[str, str]:
    try:
        reply = test_llm_connection(body.base_url, body.api_key, body.model)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"reply": reply}


@app.get("/api/profile")
def get_profile() -> Dict[str, str]:
    prefs = get_preferences() or {}
    return {
        "name": get_name() or "",
        "browser": str(prefs.get("browser", "") or ""),
        "notes": str(prefs.get("profile_notes", "") or ""),
    }


@app.put("/api/profile")
def save_profile(body: ProfileBody) -> Dict[str, str]:
    if body.name.strip():
        remember_name(body.name.strip())
    if body.browser.strip():
        set_preference("browser", body.browser.strip())
    set_preference("profile_notes", body.notes.strip())
    return get_profile()


def _mount_frontend() -> None:
    assets = _WEB_DIST / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets)), name="assets")

    @app.get("/")
    def index() -> FileResponse:
        index_path = _WEB_DIST / "index.html"
        if not index_path.exists():
            raise HTTPException(
                status_code=503,
                detail="React UI not built. Run: cd web && npm install && npm run build",
            )
        return FileResponse(index_path)

    @app.get("/{full_path:path}")
    def spa_fallback(full_path: str) -> FileResponse:
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not found")
        candidate = _WEB_DIST / full_path
        if candidate.is_file():
            return FileResponse(candidate)
        index_path = _WEB_DIST / "index.html"
        if not index_path.exists():
            raise HTTPException(status_code=503, detail="React UI not built.")
        return FileResponse(index_path)


_mount_frontend()


def start_api_server(
    host: str = "127.0.0.1",
    port: int = 8787,
    *,
    daemon: bool = True,
) -> threading.Thread:
    """Start uvicorn in a background thread."""
    import uvicorn

    config = uvicorn.Config(
        app,
        host=host,
        port=port,
        log_level="warning",
        access_log=False,
    )
    server = uvicorn.Server(config)

    thread = threading.Thread(target=server.run, name="zara-webapi", daemon=daemon)
    thread.start()
    return thread


def ui_url(host: str = "127.0.0.1", port: int = 8787) -> str:
    return f"http://{host}:{port}/"
