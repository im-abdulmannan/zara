"""TTS Engine wrapper with real-time speech interruption support (barge-in)."""
from __future__ import annotations

import threading
from typing import Optional
import pyttsx3

# Speech rate (words per minute)
RATE = 170

_FEMALE_NAME_HINTS = ("zira", "female", "hazel", "eva", "susan", "aria")


def _find_female_voice_id() -> Optional[str]:
    """Returns the id of an installed female voice, or None if none is found."""
    engine = pyttsx3.init()
    try:
        voices = engine.getProperty("voices")
        for voice in voices:
            if str(getattr(voice, "gender", "")).lower() == "female":
                return voice.id
        for voice in voices:
            if any(hint in voice.name.lower() for hint in _FEMALE_NAME_HINTS):
                return voice.id
        return None
    finally:
        engine.stop()


FEMALE_VOICE_ID = _find_female_voice_id()

_active_engine: Optional[pyttsx3.Engine] = None
_engine_lock = threading.Lock()


def speak(text: str) -> None:
    """Speak text. Can be interrupted at any point by calling stop_speech()."""
    global _active_engine
    if not text or not str(text).strip():
        return

    print(f"[SPEAK CALLED] {repr(text)}")

    with _engine_lock:
        try:
            engine = pyttsx3.init()
            engine.setProperty("rate", RATE)
            if FEMALE_VOICE_ID:
                engine.setProperty("voice", FEMALE_VOICE_ID)

            _active_engine = engine
        except Exception as exc:
            print(f"Failed to initialize TTS engine: {exc}")
            return

    try:
        engine.say(str(text))
        engine.runAndWait()
    except Exception as exc:
        print(f"TTS execution error: {exc}")
    finally:
        with _engine_lock:
            if _active_engine is engine:
                _active_engine = None
            try:
                engine.stop()
            except Exception:
                pass


def stop_speech() -> None:
    """Interrupt and immediately stop active TTS speech playback."""
    global _active_engine
    with _engine_lock:
        if _active_engine is not None:
            try:
                _active_engine.stop()
                print("[TTS INTERRUPTED] Speech stopped by user barge-in.")
            except Exception as exc:
                print(f"Error stopping TTS engine: {exc}")
            _active_engine = None
