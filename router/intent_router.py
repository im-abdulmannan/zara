"""Routes classified intents to Zara tool payloads."""
from __future__ import annotations

from typing import Any, Mapping, Optional

from intent.config import IntentConfig
from intent.models import ClassificationResult, Intent
from router.logging_config import get_logger
from time_parser import parse_when
from time_parser.exceptions import TimeParseError
from time_parser.patterns import TIME_EXPRESSION_RE


class IntentRouter:
    """Maps :class:`ClassificationResult` values to executable tool payloads."""

    def __init__(self, config: IntentConfig | None = None) -> None:
        self._config = config or IntentConfig.from_env()
        self._logger = get_logger(__name__, self._config.log_level)

    @property
    def confidence_threshold(self) -> float:
        return self._config.confidence_threshold

    def route(
        self,
        user_text: str,
        classification: ClassificationResult,
    ) -> Optional[dict[str, Any]]:
        """Return a tool payload dict, or ``None`` to fall through to the LLM."""
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


def _route_reminder_create(user_text: str, entities: Mapping[str, Any]) -> Optional[dict]:
    title = _entity_str(entities, "title", "value")
    time_value = _entity_str(entities, "time", "datetime")
    if not title:
        return None
    if not time_value and not TIME_EXPRESSION_RE.search(user_text):
        return None
    when_text = time_value or user_text
    try:
        when = parse_when(when_text)
    except TimeParseError:
        return None
    return {
        "tool": "set_reminder",
        "title": title,
        "datetime": when.isoformat(),
        "time": when.strftime("%H:%M"),
        "repeat": _entity_str(entities, "repeat") or "once",
        "description": _entity_str(entities, "description"),
    }


def _route_reminder_delete(user_text: str, entities: Mapping[str, Any]) -> Optional[dict]:
    index = entities.get("index")
    title = _entity_str(entities, "title", "query")
    if index is None and not title:
        return {"tool": "list_reminders"}
    payload: dict[str, Any] = {"tool": "cancel_reminder"}
    if index is not None:
        payload["index"] = index
    if title:
        payload["title"] = title
    return payload


def _route_meeting_create(user_text: str, entities: Mapping[str, Any]) -> Optional[dict]:
    title = _entity_str(entities, "title", "value")
    if not title:
        return None
    date_value = _entity_str(entities, "date") or "today"
    time_value = _entity_str(entities, "time") or "09:00"
    return {
        "tool": "create_meeting",
        "title": title,
        "date": date_value,
        "time": time_value,
        "location": _entity_str(entities, "location"),
        "participants": entities.get("attendees") or entities.get("participants") or "",
        "notes": _entity_str(entities, "notes"),
    }


def _route_meeting_query(user_text: str, entities: Mapping[str, Any]) -> dict:
    question = _entity_str(entities, "query", "question") or user_text
    return {"tool": "query_calendar", "question": question}


def _route_note_create(user_text: str, entities: Mapping[str, Any]) -> Optional[dict]:
    title = _entity_str(entities, "title", "value")
    content = _entity_str(entities, "content", "body", "text")
    if not title or not content:
        return None
    return {
        "tool": "create_note",
        "title": title,
        "content": content,
        "tags": entities.get("tags") or "",
    }


def _route_note_query(user_text: str, entities: Mapping[str, Any]) -> dict:
    query = _entity_str(entities, "query", "question") or user_text
    if query.lower().strip() in {"list notes", "show notes", "my notes", "all notes"}:
        return {"tool": "list_notes"}
    return {"tool": "search_notes", "query": query}


def _route_memory_save(user_text: str, entities: Mapping[str, Any]) -> Optional[dict]:
    value = _entity_str(entities, "value", "text")
    if not value:
        return None
    kind = (_entity_str(entities, "kind") or "fact").lower()
    payload: dict[str, Any] = {
        "tool": "remember",
        "kind": kind,
        "value": value,
    }
    key = _entity_str(entities, "key")
    if key:
        payload["key"] = key
    return payload


def _route_memory_query(user_text: str, entities: Mapping[str, Any]) -> dict:
    query = _entity_str(entities, "query", "question", "key")
    if not query or query.lower() in {
        "everything",
        "all",
        "what do you remember",
        "what do you know about me",
    }:
        return {"tool": "query_memory"}
    return {"tool": "query_memory", "query": query}


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
    command = (_entity_str(entities, "command") or user_text).lower()
    if "shutdown" in command or "shut down" in command:
        return {"tool": "shutdown_pc"}
    if "restart" in command or "reboot" in command:
        return {"tool": "restart_pc"}
    if "lock" in command:
        return {"tool": "lock_pc"}
    if "time" in command:
        return {"tool": "get_time"}
    return None


def _route_habit_create(user_text: str, entities: Mapping[str, Any]) -> Optional[dict]:
    title = _entity_str(entities, "title", "value")
    if not title:
        return None
    return {
        "tool": "create_habit",
        "title": title,
        "frequency": _entity_str(entities, "frequency") or "daily",
        "time": _entity_str(entities, "time") or "09:00",
    }


def _route_habit_query(user_text: str, entities: Mapping[str, Any]) -> dict:
    return {"tool": "list_habits", "include_paused": False}


def _route_habit_done(user_text: str, entities: Mapping[str, Any]) -> Optional[dict]:
    index = entities.get("index")
    title = _entity_str(entities, "title", "query")
    if index is None and not title:
        return {"tool": "list_habits", "include_paused": False}
    payload: dict[str, Any] = {"tool": "mark_habit_done"}
    if index is not None:
        payload["index"] = index
    if title:
        payload["title"] = title
    return payload


_ROUTE_HANDLERS = {
    Intent.REMINDER_CREATE: _route_reminder_create,
    Intent.REMINDER_DELETE: _route_reminder_delete,
    Intent.MEETING_CREATE: _route_meeting_create,
    Intent.MEETING_QUERY: _route_meeting_query,
    Intent.NOTE_CREATE: _route_note_create,
    Intent.NOTE_QUERY: _route_note_query,
    Intent.MEMORY_SAVE: _route_memory_save,
    Intent.MEMORY_QUERY: _route_memory_query,
    Intent.HABIT_CREATE: _route_habit_create,
    Intent.HABIT_QUERY: _route_habit_query,
    Intent.HABIT_DONE: _route_habit_done,
    Intent.OPEN_APPLICATION: _route_open_application,
    Intent.WEB_SEARCH: _route_web_search,
    Intent.SYSTEM_COMMAND: _route_system_command,
}
