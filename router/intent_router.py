"""Routes classified intents to Zara tool payloads."""
from __future__ import annotations

from typing import Any, Mapping, Optional

from intent.config import IntentConfig
from intent.models import ClassificationResult, Intent
from router.logging_config import get_logger


class IntentRouter:
    """Maps :class:`ClassificationResult` values to executable tool payloads."""

    def __init__(self, config: IntentConfig | None = None) -> None:
        self._config = config or IntentConfig.from_env()
        self._logger = get_logger(__name__, self._config.log_level)

    @property
    def config(self) -> IntentConfig:
        return self._config

    @property
    def confidence_threshold(self) -> float:
        return self._config.confidence_threshold

    def reload_settings(self, config: IntentConfig) -> None:
        """Hot-reload confidence/threshold settings from the Settings UI."""
        self._config = config
        self._logger = get_logger(__name__, self._config.log_level)
        self._logger.info(
            "Intent router reloaded confidence_threshold=%.2f enabled=%s",
            self._config.confidence_threshold,
            self._config.enabled,
        )

    def route(
        self,
        user_text: str,
        classification: ClassificationResult,
    ) -> Optional[dict[str, Any]]:
        """Return a tool payload dict, or ``None`` to fall through to the LLM."""
        if not self._config.enabled:
            return None
        if classification.intent is Intent.CHAT:
            return None
        if classification.confidence < self.confidence_threshold:
            self._logger.info(
                "Intent %s below threshold (%.2f); deferring to LLM.",
                classification.intent.value,
                classification.confidence,
            )
            return None

        entities = dict(classification.entities or {})
        handler = _ROUTE_HANDLERS.get(classification.intent)
        if handler is None:
            return None

        payload = handler(user_text, entities)
        if payload is None:
            self._logger.info(
                "Intent %s missing data; deferring to LLM.",
                classification.intent.value,
            )
            return None

        self._logger.info(
            "Routed intent=%s tool=%s",
            classification.intent.value,
            payload.get("tool"),
        )
        return payload


_default_router: IntentRouter | None = None


def get_router() -> IntentRouter:
    global _default_router
    if _default_router is None:
        _default_router = IntentRouter()
    return _default_router


def reload_router(config: IntentConfig) -> None:
    """Hot-reload the shared intent router from Settings."""
    get_router().reload_settings(config)


def route_intent(
    user_text: str,
    classification: ClassificationResult,
) -> Optional[dict[str, Any]]:
    """Route *classification* to a tool payload using the shared router."""
    return get_router().route(user_text, classification)


def _entity_str(entities: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        value = entities.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _route_open_application(user_text: str, entities: Mapping[str, Any]) -> Optional[dict]:
    app = _entity_str(entities, "app", "application")
    website = _entity_str(entities, "website", "url", "site")
    if website:
        return {"tool": "open_website", "website": website}
    if app:
        return {"tool": "open_app", "app": app}
    return None


def _route_web_search(user_text: str, entities: Mapping[str, Any]) -> Optional[dict]:
    query = _entity_str(entities, "query", "question") or user_text
    if not query:
        return None
    return {"tool": "search_google", "query": query}


def _route_system_command(user_text: str, entities: Mapping[str, Any]) -> Optional[dict]:
    from tools.registry import get_registry

    command = (_entity_str(entities, "command") or user_text).lower()
    tool = get_registry().find_by_intent_text(command)
    if tool is not None:
        return {"tool": tool.name}
    return None


_ROUTE_HANDLERS = {
    Intent.OPEN_APPLICATION: _route_open_application,
    Intent.WEB_SEARCH: _route_web_search,
    Intent.SYSTEM_COMMAND: _route_system_command,
}
