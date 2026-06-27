import pyttsx3

# Speech rate (words per minute-ish). 170 matches the previous setting.
RATE = 170

# Known female voice name hints, used as a fallback when a voice does not
# report its gender explicitly.
_FEMALE_NAME_HINTS = ("zira", "female", "hazel", "eva", "susan", "aria")


def _find_female_voice_id():
    """Returns the id of an installed female voice, or None if none is found.

    Prefers a voice that reports ``gender == "Female"`` (e.g. Microsoft Zira),
    then falls back to matching known female voice names.
    """
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


# Discover the female voice once at import rather than on every call.
FEMALE_VOICE_ID = _find_female_voice_id()


def speak(text):
    print(f"[SPEAK CALLED] {repr(text)}")

    engine = pyttsx3.init()
    engine.setProperty("rate", RATE)

    if FEMALE_VOICE_ID:
        engine.setProperty("voice", FEMALE_VOICE_ID)

    engine.say(str(text))
    engine.runAndWait()
    engine.stop()
