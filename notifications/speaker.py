"""Speaker output adapters.

The :class:`Speaker` protocol abstracts "turn text into speech". Every concrete
speaker guards :meth:`speak` with a lock so that two callers can never speak at
once -- this is the mechanism that *prevents interruption while TTS is already
speaking*. The same speaker instance (and therefore the same lock) should be
shared with the rest of the assistant, so that the worker and normal replies
take turns instead of overlapping.

``pyttsx3``'s ``runAndWait()`` is blocking and not reentrant, so this
serialisation is mandatory, not merely cosmetic.
"""
from __future__ import annotations

import threading
from typing import Callable, Optional, Protocol, runtime_checkable

from automation.logging_config import get_logger

_logger = get_logger(__name__)


@runtime_checkable
class Speaker(Protocol):
    """Renders text as speech, one utterance at a time."""

    def speak(self, text: str) -> None:
        ...

    @property
    def is_speaking(self) -> bool:
        ...

    def wait_until_idle(self, timeout: Optional[float] = None) -> bool:
        ...


class _LockGuardedSpeaker:
    """Base class providing the shared lock + ``is_speaking`` semantics.

    Subclasses implement :meth:`_emit` to actually produce sound. A
    :class:`threading.Lock` serialises callers; an :class:`threading.Event`
    exposes whether speech is currently in progress.
    """

    def __init__(self, lock: Optional[threading.Lock] = None) -> None:
        # Allow an external lock to be injected so the whole app can share one
        # "speech channel" and never talk over itself.
        self._lock = lock or threading.Lock()
        self._speaking = threading.Event()

    @property
    def is_speaking(self) -> bool:
        """True while an utterance is being spoken."""
        return self._speaking.is_set()

    @property
    def lock(self) -> threading.Lock:
        """The underlying speech lock (share this with other speakers)."""
        return self._lock

    def speak(self, text: str) -> None:
        """Speaks ``text``, blocking until finished.

        Acquiring the lock means a second caller waits here until the current
        utterance completes -- guaranteeing no interruption.
        """
        if not text or not str(text).strip():
            _logger.debug("Empty text passed to speak(); ignored.")
            return
        with self._lock:
            self._speaking.set()
            try:
                self._emit(str(text))
            finally:
                self._speaking.clear()

    def wait_until_idle(self, timeout: Optional[float] = None) -> bool:
        """Blocks until no utterance is in progress.

        Returns True if idle, False if ``timeout`` elapsed while still speaking.
        Useful for the assistant to defer its own speech until a reminder ends.
        """
        # Acquiring then releasing the lock guarantees the current utterance
        # has finished. We honour the timeout via lock.acquire(timeout=...).
        acquired = self._lock.acquire(timeout=timeout if timeout is not None else -1)
        if acquired:
            self._lock.release()
        return acquired

    def _emit(self, text: str) -> None:  # pragma: no cover - overridden
        raise NotImplementedError


class TTSSpeaker(_LockGuardedSpeaker):
    """Production speaker backed by the project's TTS (``voice.tts.speak``)."""

    def __init__(
        self,
        speak_func: Optional[Callable[[str], None]] = None,
        lock: Optional[threading.Lock] = None,
    ) -> None:
        super().__init__(lock=lock)
        self._speak_func = speak_func

    def _emit(self, text: str) -> None:
        speak_func = self._speak_func
        if speak_func is None:
            # Imported lazily so this package does not hard-depend on the voice
            # subsystem (and stays importable in headless tests).
            from voice.tts import speak as speak_func  # type: ignore
        _logger.info("Speaking: %r", text)
        speak_func(text)


class ConsoleSpeaker(_LockGuardedSpeaker):
    """Test/headless speaker that prints instead of producing audio.

    Optionally simulates speech duration so concurrency behaviour can be
    observed without a sound card.
    """

    def __init__(
        self,
        speak_duration: float = 0.0,
        lock: Optional[threading.Lock] = None,
    ) -> None:
        super().__init__(lock=lock)
        self._speak_duration = speak_duration

    def _emit(self, text: str) -> None:
        import time

        print(f"[SPEAKER] {text}")
        if self._speak_duration > 0:
            time.sleep(self._speak_duration)
