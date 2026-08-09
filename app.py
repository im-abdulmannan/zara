"""Terminal text entry point — type a request, press Enter (no STT/TTS)."""
from __future__ import annotations

import signal
import sys

from brain.planner import Planner
from core.logging_config import get_logger
from core.session import Session
from runtime import get_runtime, shutdown_runtime

_logger = get_logger(__name__)

_QUIT_WORDS = {"quit", "exit", "q", "bye", "goodbye"}


def _mute_tts(runtime) -> None:
    """Disable pyttsx3 — keep the speaker lock but never produce audio."""
    runtime.speaker._speak_func = lambda _text: None


def _print_reply(text: str) -> None:
    cleaned = (text or "").strip()
    if not cleaned:
        cleaned = "(no reply)"
    print(f"\nZara: {cleaned}\n")


def main() -> None:
    runtime = get_runtime()
    _mute_tts(runtime)

    planner = Planner()
    session = Session(continuous_mode=True, interruptible=False)
    shutting_down = False

    def _quit_zara(*_args) -> None:
        nonlocal shutting_down
        if shutting_down:
            return
        shutting_down = True
        print("\nShutting down Zara...")
        shutdown_runtime()

    signal.signal(signal.SIGINT, _quit_zara)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _quit_zara)

    from agent import get_active_connection_summary

    print("Zara text mode (STT/TTS disabled)")
    print(f"Model: {get_active_connection_summary()}")
    print('Type a request and press Enter. Examples:')
    print('  find the zara folder from drive D')
    print('  what time is it')
    print("Type quit or press Ctrl+C to exit.\n")

    try:
        while not shutting_down:
            try:
                user_text = input("You> ").strip()
            except EOFError:
                break

            if not user_text:
                continue
            if user_text.lower() in _QUIT_WORDS:
                break

            try:
                result = planner.plan_and_execute(user_text, session)
            except Exception:
                _logger.exception("Failed to handle: %r", user_text)
                _print_reply("Sorry, something went wrong handling that.")
                continue

            session.add_user_turn(user_text)
            session.add_assistant_turn(result.spoken_text)
            _print_reply(result.spoken_text)

            if result.awaiting_confirmation:
                print("(Waiting for yes/no confirmation)")
    except KeyboardInterrupt:
        pass
    finally:
        if not shutting_down:
            _quit_zara()


if __name__ == "__main__":
    main()
