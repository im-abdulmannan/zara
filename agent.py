import json
from datetime import datetime

from openai import OpenAI

from config import (
    OPENROUTER_API_KEY,
    MODEL_NAME
)
from intent import classify_intent
from memory.memory import load_history, save_history
from memory.store import memory_summary, auto_capture
from router import route_intent
from tools.registry import get_registry

client = OpenAI(
    api_key=OPENROUTER_API_KEY,
    base_url="https://openrouter.ai/api/v1"
)

_GROUNDING_RULES = """
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
- For multi-step requests, return {"tools": [...], "response": "..."}.
  Example: create_folder then open_folder for "create X and open it".

Never return markdown.
Never return explanations.
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

FALLBACK_MODELS = [
    MODEL_NAME,
    "meta-llama/llama-3-8b-instruct:free",
    "qwen/qwen-2-7b-instruct:free",
    "mistralai/mistral-7b-instruct:free"
]

conversation = load_history()

def ask_agent(user_text):

    # Deterministically capture memory-worthy statements before anything
    # else, so it is saved even when the model ignores the remember tool.
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

    # Intent router: dispatch directly to the correct module when confident.
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

    messages.extend(
        conversation[-20:]
    )

    reply = None
    last_error = None

    for model in FALLBACK_MODELS:
        if not model:
            continue
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages
            )
            reply = response.choices[0].message.content
            if reply:
                break
        except Exception as e:
            print(f"Warning: Model {model} failed: {e}")
            last_error = e
            continue

    if reply is None:
        raise last_error or RuntimeError("All models in the fallback chain failed.")

    conversation.append({
        "role": "assistant",
        "content": reply
    })
    save_history(conversation)

    return reply
