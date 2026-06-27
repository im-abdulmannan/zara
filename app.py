from config import WAKE_WORD
from voice.session import SessionPhase, VoiceSession

from agent import ask_agent
from tools.executor import execute_plan, parse_agent_payload, spoken_response
from runtime import get_runtime, shutdown_runtime


# Pipeline: Voice -> STT -> Intent Classifier -> Tool Router -> Module
#                                    \-> LLM (fallback) -> Tool Router -> Module

# Start background services (scheduler, reminder service, notification worker)
# and reuse the runtime's shared, lock-guarded speaker for all assistant
# speech, so spoken reminders and replies take turns instead of overlapping.
runtime = get_runtime()
speak = runtime.speak

speak("Hello, I am Zara.")

WAKE_PHRASES = [
    "hello zara",
    "hi zara",
    "hey zara",
    "zara",
]
if WAKE_WORD and WAKE_WORD.strip().lower() not in WAKE_PHRASES:
    WAKE_PHRASES.append(WAKE_WORD.strip().lower())

SLEEP_PHRASES = [
    "sleep zara",
    "go to sleep",
    "you can sleep",
    "goodbye zara",
    "stop listening",
]

session = VoiceSession(
    wake_phrases=WAKE_PHRASES,
    sleep_phrases=SLEEP_PHRASES,
)


def handle_command(text: str) -> None:
    """Run the agent pipeline and speak the result."""
    result = ask_agent(text)
    print(result)

    result = result.strip()
    if result.startswith("```"):
        result = (
            result.replace("```json", "").replace("```", "").strip()
        )

    action = parse_agent_payload(result)

    if action.get("tool") == "chat" or (
        not action.get("tool") and not action.get("tools")
    ):
        speak(action.get("response") or "Okay.")
    elif action.get("tool") or action.get("tools"):
        plan = execute_plan(action)
        speak(spoken_response(plan, action))
    else:
        speak("I didn't understand the response.")


try:
    while True:
        # 1. Wait for wake word (VAD — no fixed timer)
        wake_turn = session.listen_for_wake()
        if wake_turn is None:
            continue

        speak("I'm listening.")

        # 2. Wait for user speech, record with VAD, end on ~2s silence
        turn = session.listen_for_command()
        if turn is None or not turn.text:
            speak("I didn't hear anything.")
            session.finish_turn()
            continue

        text = turn.text.lower().strip()

        # Optional sleep command
        if session.is_sleep_command(text):
            speak("Going to sleep.")
            session.finish_turn()
            continue

        session.set_phase(SessionPhase.PROCESSING)

        try:
            handle_command(text)
        except Exception as e:
            print("ERROR:", e)
            speak("Something went wrong.")

        # 3. Return to wake-word mode
        session.finish_turn()

except KeyboardInterrupt:
    print("\nShutting down Zara...")

finally:
    shutdown_runtime()
