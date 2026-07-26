import json
import os
from datetime import datetime

from openai import APIStatusError, OpenAI, RateLimitError

from config import OPENROUTER_API_KEY, MODEL_NAME
from core.llm_config import (
    DEFAULT_OPENROUTER_URL,
    LlmConnection,
    connection_from_env,
)
from intent.config import IntentConfig
from intent import classify_intent
from memory.memory import load_history, save_history
from memory.store import memory_summary, auto_capture
from router import route_intent
from tools.registry import get_registry

_active = connection_from_env()
if not _active.api_key and OPENROUTER_API_KEY:
    _active.api_key = OPENROUTER_API_KEY
if not _active.model and MODEL_NAME:
    _active.model = MODEL_NAME

client = OpenAI(
    api_key=_active.api_key or "not-needed",
    base_url=_active.base_url or DEFAULT_OPENROUTER_URL,
)


def get_active_model() -> str | None:
    """Return the currently preferred model slug."""
    return _active.model or os.getenv("MODEL_NAME") or MODEL_NAME


def get_active_base_url() -> str:
    return (_active.base_url or os.getenv("LLM_BASE_URL") or DEFAULT_OPENROUTER_URL).rstrip("/")


def get_active_connection_summary() -> str:
    return f"{_active.label} · {_active.model} @ {get_active_base_url()}"


def apply_llm_connection(connection: LlmConnection) -> None:
    """Hot-swap the live OpenAI-compatible client from Settings."""
    global client, _active
    intent_backend = (connection.intent_backend or "gemini").lower()
    if intent_backend not in {"gemini", "openai"}:
        intent_backend = "gemini"
    intent_key = (connection.intent_api_key or connection.gemini_api_key or "").strip()

    _active = LlmConnection(
        provider_id=connection.provider_id,
        label=connection.label,
        base_url=(connection.base_url or DEFAULT_OPENROUTER_URL).rstrip("/"),
        api_key=connection.api_key or "",
        model=connection.model.strip(),
        gemini_api_key=intent_key if intent_backend == "gemini" else (connection.gemini_api_key or ""),
        intent_enabled=bool(connection.intent_enabled),
        intent_backend=intent_backend,
        intent_provider_id=connection.intent_provider_id or "openrouter",
        intent_base_url=(connection.intent_base_url or "").rstrip("/"),
        intent_api_key=intent_key,
        intent_model=(connection.intent_model or "gemini-2.0-flash").strip(),
        intent_confidence=max(0.0, min(1.0, float(connection.intent_confidence))),
    )
    os.environ["LLM_PROVIDER"] = _active.provider_id
    os.environ["LLM_BASE_URL"] = _active.base_url
    os.environ["LLM_API_KEY"] = _active.api_key
    os.environ["MODEL_NAME"] = _active.model
    os.environ["INTENT_ENABLED"] = "true" if _active.intent_enabled else "false"
    os.environ["INTENT_BACKEND"] = _active.intent_backend
    os.environ["INTENT_PROVIDER"] = _active.intent_provider_id
    os.environ["INTENT_BASE_URL"] = _active.intent_base_url
    os.environ["INTENT_API_KEY"] = _active.intent_api_key
    os.environ["INTENT_MODEL"] = _active.intent_model
    os.environ["INTENT_CONFIDENCE_THRESHOLD"] = f"{_active.intent_confidence:.2f}"
    if "openrouter.ai" in _active.base_url:
        os.environ["OPENROUTER_API_KEY"] = _active.api_key

    client = OpenAI(
        api_key=_active.api_key or "not-needed",
        base_url=_active.base_url,
    )

    if _active.intent_backend == "gemini":
        os.environ["GEMINI_API_KEY"] = _active.intent_api_key
        os.environ["GOOGLE_API_KEY"] = _active.intent_api_key

    intent_config = IntentConfig(
        enabled=_active.intent_enabled,
        backend=_active.intent_backend,
        api_key=_active.intent_api_key,
        model=_active.intent_model,
        base_url=_active.intent_base_url,
        confidence_threshold=_active.intent_confidence,
    )
    try:
        from intent.classifier import reload_settings

        reload_settings(config=intent_config)
    except Exception as exc:
        print(f"Failed to reload intent classifier: {exc}")
    try:
        from router.intent_router import reload_router

        reload_router(intent_config)
    except Exception as exc:
        print(f"Failed to reload intent router: {exc}")


def reload_runtime_credentials(
    *,
    openrouter_api_key: str | None = None,
    model_name: str | None = None,
    gemini_api_key: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
    provider_id: str | None = None,
    intent_model: str | None = None,
    intent_confidence: float | None = None,
) -> None:
    """Backward-compatible Settings apply helper."""
    current = LlmConnection(
        provider_id=provider_id or _active.provider_id,
        label=_active.label,
        base_url=base_url or _active.base_url,
        api_key=api_key if api_key is not None else (
            openrouter_api_key if openrouter_api_key is not None else _active.api_key
        ),
        model=model_name if model_name is not None else _active.model,
        gemini_api_key=gemini_api_key if gemini_api_key is not None else _active.gemini_api_key,
        intent_enabled=_active.intent_enabled,
        intent_backend=_active.intent_backend,
        intent_provider_id=_active.intent_provider_id,
        intent_base_url=_active.intent_base_url,
        intent_api_key=(
            gemini_api_key if gemini_api_key is not None else _active.intent_api_key
        ),
        intent_model=intent_model if intent_model is not None else _active.intent_model,
        intent_confidence=(
            intent_confidence if intent_confidence is not None else _active.intent_confidence
        ),
    )
    apply_llm_connection(current)


_GROUNDING_RULES = """
IDENTITY (always true):
- Your name is Zara, a voice-first Windows desktop assistant.
- Wake phrases: "Hey Zara", "Hello Zara", "Hi Zara", or just "Zara".
- Sleep phrases: "Sleep Zara", "Go to sleep", "Goodbye Zara", "Stop listening".
- After wake, continuous conversation stays active until sleep or idle timeout.
- Never claim you have no wake word. Never invent a different wake word.

GROUNDING RULES (very important):
- You have NO email or live web data. The current date and time is
  provided to you; use it for reminders. The only other things you know
  about the user are in the "What you know about the user" section.
- For calendar, meeting, and reminder questions, ALWAYS use
  query_calendar. Never invent meetings or schedule items.
- Never invent times, appointments, or facts.
- If asked about something you have not been told and is not available
  via a tool, say you don't have that information. Do NOT guess.
- For questions about tasks stored in memory, answer ONLY from the
  stored "Ongoing tasks". If there are none, say there are none.
- Use set_reminder for timed reminders; use remember for durable facts.
- When the user asks to find/locate a project, folder, or file on this PC,
  call search_files with query set to the name (e.g. {"tool":"search_files","query":"zara","kind":"folder"}).
  Do NOT ask them for the path first if they said they don't know it.
- Put tool arguments at the top level next to "tool" (not nested under "params").
- For multi-step requests, return {"tools": [...], "response": "..."}.
  Example: create_folder then open_folder for "create X and open it".
- Spoken replies must be plain English only (no Arabic/Urdu mixed in).

Never return markdown.
Never return explanations outside JSON.
Return JSON only.
"""


def build_system_prompt() -> str:
    """Build the LLM system prompt from the live tool registry."""
    return (
        "You are Zara, a desktop AI assistant for Windows.\n\n"
        + get_registry().build_system_prompt_section()
        + "\n"
        + _GROUNDING_RULES
    )


# Prefer the free-model router only when talking to OpenRouter.
MODEL_FALLBACKS = [
    "openrouter/free",
    "openai/gpt-oss-20b:free",
    "google/gemma-4-31b-it:free",
    "google/gemma-4-26b-a4b-it:free",
    "meta-llama/llama-3.3-70b-instruct:free",
]


def _uses_openrouter() -> bool:
    return "openrouter.ai" in get_active_base_url()


def _model_chain() -> list[str]:
    """Primary model, then OpenRouter fallbacks when applicable."""
    chain: list[str] = []
    seen: set[str] = set()
    primary = get_active_model()
    extras = MODEL_FALLBACKS if _uses_openrouter() else []
    for model in ([primary] if primary else []) + extras:
        if model and model not in seen:
            seen.add(model)
            chain.append(model)
    return chain


def _is_rate_limited(exc: Exception) -> bool:
    if isinstance(exc, RateLimitError):
        return True
    return isinstance(exc, APIStatusError) and exc.status_code == 429


def _log_model_failure(model: str, exc: Exception) -> None:
    if _is_rate_limited(exc):
        print(f"{model} rate limited (429), trying next model...")
    else:
        print(f"{model} failed: {exc}")


conversation = load_history()

LOCAL_OFFLINE_SERVERS = [
    ("http://localhost:11434/v1", "qwen2.5-coder:latest"),
    ("http://localhost:11434/v1", "llama3.2:latest"),
    ("http://localhost:1234/v1", "local-model"),
]


def _try_local_offline_llm(messages: list[dict]) -> str | None:
    """Fallback to local offline LLM server when cloud fails."""
    for base_url, model in LOCAL_OFFLINE_SERVERS:
        try:
            local_client = OpenAI(base_url=base_url, api_key="ollama", timeout=4.0)
            resp = local_client.chat.completions.create(
                model=model,
                messages=messages,
            )
            if resp.choices and resp.choices[0].message.content:
                print(f"Offline local LLM ({model} @ {base_url}) responded.")
                return resp.choices[0].message.content
        except Exception:
            continue
    return None


def ask_agent(user_text):
    captured = auto_capture(user_text)
    if captured:
        print("Remembered:", "; ".join(captured))

    classification = classify_intent(user_text)
    print("Intent classification:", json.dumps(classification.to_dict()))

    conversation.append({
        "role": "user",
        "content": user_text
    })
    save_history(conversation)

    routed = route_intent(user_text, classification)
    if routed is not None:
        reply = json.dumps(routed)
        print("Intent route:", reply)
        conversation.append({"role": "assistant", "content": reply})
        save_history(conversation)
        return reply

    intent_context = (
        "Pre-classified user intent (use as routing hint):\n"
        + json.dumps(classification.to_dict(), indent=2)
    )

    messages = [
        {
            "role": "system",
            "content": build_system_prompt()
        },
        {
            "role": "system",
            "content": (
                intent_context
                + "\n\nCurrent date and time: "
                + datetime.now().strftime("%A %Y-%m-%d %H:%M")
                + "\n\nWhat you know about the user:\n"
                + memory_summary()
            )
        }
    ]

    messages.extend(conversation[-20:])

    reply = None
    for model in _model_chain():
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
            )
            reply = response.choices[0].message.content
            if reply:
                break
        except Exception as exc:
            _log_model_failure(model, exc)
            continue

    if reply is None:
        reply = _try_local_offline_llm(messages)

    if reply is None:
        raise RuntimeError("All models (cloud and offline local fallbacks) failed.")

    conversation.append({
        "role": "assistant",
        "content": reply
    })
    save_history(conversation)

    return reply
