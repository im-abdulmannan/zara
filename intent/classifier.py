"""Intent classifier for Zara — Gemini native or any OpenAI-compatible LLM."""
from __future__ import annotations

import json
import re
from typing import Any, Optional

from intent.config import IntentConfig
from intent.exceptions import IntentClassificationError
from intent.logging_config import get_logger
from intent.models import ClassificationResult, Intent

CLASSIFICATION_PROMPT = """You are an intent classifier for Zara, a desktop voice assistant.

Classify the user message into exactly ONE intent from this list:

- CHAT: general conversation, greetings, questions, chit-chat, or anything that does not fit another intent
- REMINDER_CREATE: set a reminder, alarm, or timed notification (e.g. "remind me at 5pm to call mom")
- REMINDER_DELETE: cancel, remove, or delete a reminder (e.g. "cancel my first reminder")
- MEETING_CREATE: schedule or create a meeting or appointment
- MEETING_QUERY: ask about meetings or appointments (e.g. "what meetings do I have today?")
- NOTE_CREATE: create, save, or write a note
- NOTE_QUERY: find, read, or search notes
- MEMORY_SAVE: tell Zara to remember a fact, preference, name, or task (not a timed reminder)
- MEMORY_QUERY: ask what Zara remembers about the user
- HABIT_CREATE: create or track a recurring habit (e.g. "track drinking water daily at 7am")
- HABIT_QUERY: list or ask about habits
- HABIT_DONE: mark a habit as done or completed today
- OPEN_APPLICATION: open an app or website (e.g. "open chrome", "launch vscode", "go to youtube")
- WEB_SEARCH: search the web or Google for information
- SYSTEM_COMMAND: shutdown, restart, lock the PC, or ask for the current time

Extract relevant entities when present. Use empty object {} when none apply.

Entity keys by intent:
- REMINDER_CREATE: title, time, repeat (once|daily|weekly|monthly)
- REMINDER_DELETE: index, title
- MEETING_CREATE: title, date, time, attendees
- MEETING_QUERY: date, query
- NOTE_CREATE: title, content
- NOTE_QUERY: query
- MEMORY_SAVE: kind (name|preference|fact|task), key, value
- MEMORY_QUERY: query
- HABIT_CREATE: title, frequency (daily|weekday|weekend|weekly|monthly), time
- HABIT_QUERY: none
- HABIT_DONE: index, title
- OPEN_APPLICATION: app, website
- WEB_SEARCH: query
- SYSTEM_COMMAND: command (shutdown|restart|lock|get_time)
- CHAT: none

Return ONLY valid JSON with this exact shape:
{
  "intent": "<INTENT_NAME>",
  "confidence": 0.95,
  "entities": {}
}

Rules:
- confidence is a float from 0.0 to 1.0 reflecting how sure you are
- intent must be one of the listed names exactly (uppercase)
- entities must be a JSON object (not an array)
- prefer REMINDER_CREATE over MEMORY_SAVE when a specific time is mentioned
- prefer OPEN_APPLICATION over WEB_SEARCH when the user wants to open something directly

User message:
"""

_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "intent": {
            "type": "string",
            "enum": [member.value for member in Intent],
        },
        "confidence": {"type": "number"},
        "entities": {"type": "object"},
    },
    "required": ["intent", "confidence", "entities"],
}

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def _strip_markdown_fences(text: str) -> str:
    return _FENCE_RE.sub("", text.strip()).strip()


def _parse_response(raw: str) -> dict[str, Any]:
    cleaned = _strip_markdown_fences(raw)
    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start >= 0 and end > start:
            payload = json.loads(cleaned[start : end + 1])
        else:
            raise IntentClassificationError("Invalid JSON from classifier.")
    if not isinstance(payload, dict):
        raise IntentClassificationError("Classifier response must be a JSON object.")
    return payload


def _normalise_confidence(value: Any) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, confidence))


def _normalise_entities(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return {str(k): v for k, v in value.items() if v is not None}


def _apply_confidence_fallback(
    result: ClassificationResult,
    threshold: float,
) -> ClassificationResult:
    if result.confidence >= threshold:
        return result
    return ClassificationResult.chat_fallback(confidence=result.confidence)


class IntentClassifier:
    """Classifies user text into intents via Gemini or OpenAI-compatible LLMs."""

    def __init__(self, config: IntentConfig | None = None) -> None:
        self._config = config or IntentConfig.from_env()
        self._logger = get_logger(__name__, self._config.log_level)
        self._gemini_client = None
        self._openai_client = None
        self._rebuild_clients()

    @property
    def config(self) -> IntentConfig:
        return self._config

    def _rebuild_clients(self) -> None:
        self._gemini_client = None
        self._openai_client = None

        if not self._config.enabled:
            self._logger.info("Intent classification disabled.")
            return

        if self._config.uses_gemini:
            if self._config.api_key:
                from google import genai

                self._gemini_client = genai.Client(api_key=self._config.api_key)
            else:
                self._logger.warning(
                    "Intent Gemini backend enabled but no API key; falling back to CHAT."
                )
            return

        # OpenAI-compatible backend
        if not self._config.base_url:
            self._logger.warning(
                "Intent OpenAI backend enabled but INTENT_BASE_URL is empty; falling back to CHAT."
            )
            return
        from openai import OpenAI

        self._openai_client = OpenAI(
            api_key=self._config.api_key or "not-needed",
            base_url=self._config.base_url.rstrip("/"),
            timeout=20.0,
        )

    def reload_api_key(self, api_key: str) -> None:
        """Hot-reload the API key (keeps other settings)."""
        self.reload_settings(api_key=api_key)

    def reload_settings(
        self,
        *,
        enabled: bool | None = None,
        backend: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        confidence_threshold: float | None = None,
        config: IntentConfig | None = None,
    ) -> None:
        """Hot-reload intent classifier settings from the Settings UI."""
        if config is not None:
            self._config = config
            self._rebuild_clients()
            self._logger.info(
                "Intent settings reloaded enabled=%s backend=%s model=%s confidence=%.2f",
                self._config.enabled,
                self._config.backend,
                self._config.model,
                self._config.confidence_threshold,
            )
            return

        key = self._config.api_key if api_key is None else (api_key or "").strip()
        intent_model = (
            self._config.model if model is None else (model or "").strip() or self._config.model
        )
        threshold = (
            self._config.confidence_threshold
            if confidence_threshold is None
            else max(0.0, min(1.0, float(confidence_threshold)))
        )
        next_backend = (backend or self._config.backend or "gemini").lower()
        if next_backend not in {"gemini", "openai"}:
            next_backend = "gemini"
        next_base = self._config.base_url if base_url is None else (base_url or "").strip()
        next_enabled = self._config.enabled if enabled is None else bool(enabled)

        self._config = IntentConfig(
            enabled=next_enabled,
            backend=next_backend,
            api_key=key,
            model=intent_model,
            base_url=next_base,
            confidence_threshold=threshold,
            log_level=self._config.log_level,
        )
        self._rebuild_clients()
        self._logger.info(
            "Intent settings reloaded enabled=%s backend=%s model=%s confidence=%.2f",
            next_enabled,
            next_backend,
            intent_model,
            threshold,
        )

    def classify(self, user_text: str) -> ClassificationResult:
        """Classify *user_text* and return a structured result."""
        text = (user_text or "").strip()
        if not text:
            return ClassificationResult.chat_fallback(confidence=1.0)

        if not self._config.enabled:
            return ClassificationResult.chat_fallback(confidence=0.0)

        try:
            if self._config.uses_gemini:
                payload = self._classify_gemini(text)
            else:
                payload = self._classify_openai(text)
        except Exception as exc:
            message = str(exc)
            if "429" in message or "RESOURCE_EXHAUSTED" in message or "quota" in message.lower():
                self._logger.warning(
                    "Intent quota/rate-limit hit; falling back to main LLM. "
                    "Disable Intent or switch INTENT_MODEL / INTENT_API_KEY in .env."
                )
            else:
                self._logger.warning("Intent classification failed: %s", message)
            return ClassificationResult.chat_fallback(confidence=0.0)

        intent = Intent.from_value(payload.get("intent", Intent.CHAT.value))
        confidence = _normalise_confidence(payload.get("confidence", 0.0))
        entities = _normalise_entities(payload.get("entities", {}))

        result = ClassificationResult(
            intent=intent,
            confidence=confidence,
            entities=entities,
        )
        final = _apply_confidence_fallback(result, self._config.confidence_threshold)

        if final.intent is Intent.CHAT and result.intent is not Intent.CHAT:
            self._logger.info(
                "Low confidence (%.2f < %.2f); falling back from %s to CHAT.",
                result.confidence,
                self._config.confidence_threshold,
                result.intent.value,
            )
        else:
            self._logger.info(
                "Classified intent=%s confidence=%.2f entities=%s backend=%s",
                final.intent.value,
                final.confidence,
                final.entities,
                self._config.backend,
            )

        return final

    def _classify_gemini(self, text: str) -> dict[str, Any]:
        if self._gemini_client is None:
            raise IntentClassificationError("Gemini client is not configured.")

        prompt = CLASSIFICATION_PROMPT + text
        response = self._gemini_client.models.generate_content(
            model=self._config.model,
            contents=prompt,
            config={
                "temperature": 0.1,
                "response_mime_type": "application/json",
                "response_json_schema": _RESPONSE_SCHEMA,
            },
        )
        raw = (response.text or "").strip()
        if not raw:
            raise IntentClassificationError("Empty response from Gemini.")
        return _parse_response(raw)

    def _classify_openai(self, text: str) -> dict[str, Any]:
        if self._openai_client is None:
            raise IntentClassificationError("OpenAI-compatible intent client is not configured.")
        if not self._config.model:
            raise IntentClassificationError("Intent model is required.")

        response = self._openai_client.chat.completions.create(
            model=self._config.model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a strict JSON intent classifier. "
                        "Return only valid JSON, no markdown."
                    ),
                },
                {"role": "user", "content": CLASSIFICATION_PROMPT + text},
            ],
            temperature=0.1,
        )
        raw = ""
        if response.choices:
            raw = (response.choices[0].message.content or "").strip()
        if not raw:
            raise IntentClassificationError("Empty response from intent LLM.")
        return _parse_response(raw)


_default_classifier: Optional[IntentClassifier] = None


def get_classifier() -> IntentClassifier:
    """Return the process-wide singleton classifier."""
    global _default_classifier
    if _default_classifier is None:
        _default_classifier = IntentClassifier()
    return _default_classifier


def classify_intent(user_text: str) -> ClassificationResult:
    """Classify *user_text* using the shared classifier."""
    return get_classifier().classify(user_text)


def reload_api_key(api_key: str) -> None:
    """Reload the shared classifier API key from the Settings UI."""
    get_classifier().reload_api_key(api_key)


def reload_settings(
    *,
    enabled: bool | None = None,
    backend: str | None = None,
    api_key: str | None = None,
    model: str | None = None,
    base_url: str | None = None,
    confidence_threshold: float | None = None,
    config: IntentConfig | None = None,
) -> None:
    """Reload shared classifier settings."""
    get_classifier().reload_settings(
        enabled=enabled,
        backend=backend,
        api_key=api_key,
        model=model,
        base_url=base_url,
        confidence_threshold=confidence_threshold,
        config=config,
    )
