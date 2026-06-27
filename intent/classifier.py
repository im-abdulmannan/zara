"""Gemini-powered intent classifier for Zara user requests."""
from __future__ import annotations

import json
import re
from typing import Any

from google import genai

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
    except json.JSONDecodeError as exc:
        raise IntentClassificationError(f"Invalid JSON from classifier: {exc}") from exc
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
    """Classifies user text into intents using Gemini."""

    def __init__(self, config: IntentConfig | None = None) -> None:
        self._config = config or IntentConfig.from_env()
        self._logger = get_logger(__name__, self._config.log_level)
        self._client: genai.Client | None = None

        if self._config.api_key:
            self._client = genai.Client(api_key=self._config.api_key)
        else:
            self._logger.warning(
                "GEMINI_API_KEY / GOOGLE_API_KEY not set; classifier will fall back to CHAT."
            )

    @property
    def config(self) -> IntentConfig:
        return self._config

    def classify(self, user_text: str) -> ClassificationResult:
        """Classify *user_text* and return a structured result."""
        text = (user_text or "").strip()
        if not text:
            return ClassificationResult.chat_fallback(confidence=1.0)

        if self._client is None:
            return ClassificationResult.chat_fallback(confidence=0.0)

        prompt = CLASSIFICATION_PROMPT + text

        try:
            response = self._client.models.generate_content(
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
            payload = _parse_response(raw)
        except Exception as exc:
            self._logger.warning("Intent classification failed: %s", exc)
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
                "Classified intent=%s confidence=%.2f entities=%s",
                final.intent.value,
                final.confidence,
                final.entities,
            )

        return final


_default_classifier: IntentClassifier | None = None


def get_classifier() -> IntentClassifier:
    """Return the process-wide singleton classifier."""
    global _default_classifier
    if _default_classifier is None:
        _default_classifier = IntentClassifier()
    return _default_classifier


def classify_intent(user_text: str) -> ClassificationResult:
    """Classify *user_text* using the shared Gemini classifier."""
    return get_classifier().classify(user_text)
