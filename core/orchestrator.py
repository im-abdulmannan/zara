"""Event-driven voice assistant orchestrator."""
from __future__ import annotations

import threading
import time
from typing import Callable, List, Optional

import numpy as np

from brain.planner import Planner
from core.config import AssistantConfig
from core.event_bus import Event, EventBus, EventType
from core.logging_config import get_logger
from core.session import Session
from core.state_manager import AssistantState, StateManager
from voice.stt import WhisperTranscriber
from voice.vad_listener import CapturePhase, VadListener
from voice.wake_word import WakeWordDetector

_logger = get_logger(__name__)

# Consecutive VAD speech frames required before interrupting TTS (~300ms at 30ms chunks).
_BARGE_IN_SPEECH_FRAMES = 10
# Ignore mic echo for a short grace period after TTS starts.
_BARGE_IN_GRACE_SEC = 1.5
# End-of-utterance silence before trying Whisper wake-phrase match.
_WAKE_STT_SILENCE_SEC = 0.6


class VoiceOrchestrator:
    """Production voice loop: wake word -> VAD capture -> plan -> speak.

    All state changes go through :class:`StateManager`. Voice, brain, and
    runtime modules communicate via :class:`EventBus` events where practical.
    """

    def __init__(
        self,
        config: AssistantConfig,
        *,
        speak: Callable[[str], None],
        stop_speech: Callable[[], None] | None = None,
        planner: Planner | None = None,
        transcriber: WhisperTranscriber | None = None,
        bus: EventBus | None = None,
        session: Session | None = None,
    ) -> None:
        self.config = config
        self._speak = speak
        self._stop_speech = stop_speech
        self._planner = planner or Planner()
        self._transcriber = transcriber or WhisperTranscriber(config=config.voice)
        self.bus = bus or EventBus()
        self.session = session or Session(
            continuous_mode=config.continuous_conversation,
            interruptible=True,
        )
        self.state = StateManager(self.bus)
        self.wake_detector = WakeWordDetector(
            phrases=config.wake_phrases,
            sleep_phrases=config.sleep_phrases,
            use_streaming=config.use_streaming_wake,
            streaming_threshold=config.streaming_wake_threshold,
            streaming_models=config.streaming_wake_models,
        )
        self._vad = VadListener(
            config=config.voice,
            bus=self.bus,
            minimum_speech_duration=config.minimum_speech_duration,
        )
        self._running = False
        # Command spoken in the same utterance as the wake phrase (e.g. "Hey Zara, how are you?").
        self._pending_command: Optional[str] = None
        self._wire_logging_handlers()

    def set_continuous_mode(self, enabled: bool) -> None:
        """Enable or disable follow-up listening without a wake word."""
        self.session.continuous_mode = enabled
        _logger.info("Continuous conversation mode set to %s", enabled)

    def _wire_logging_handlers(self) -> None:
        """Subscribe lightweight observers for observability."""

        @self.bus.on(EventType.STATE_CHANGED)
        def _log_state(event: Event) -> None:
            payload = event.payload
            _logger.debug(
                "state_changed %s -> %s",
                payload.get("from"),
                payload.get("to"),
            )

    def run(self) -> None:
        """Blocking main loop until :meth:`stop` or keyboard interrupt."""
        self._running = True
        _logger.info("Voice orchestrator started")

        while self._running:
            try:
                if not self._run_idle_wake_cycle():
                    continue
                while self._running:
                    if not self._run_command_cycle():
                        self._end_conversation()
                        break
            except Exception:
                _logger.exception("Unhandled orchestrator error")
                self._recover_from_error()

        _logger.info("Voice orchestrator stopped")

    def stop(self) -> None:
        self._running = False

    def _run_idle_wake_cycle(self) -> bool:
        """Wait for wake word. Returns False to retry, True when awake."""
        self.state.transition(AssistantState.IDLE, reason="awaiting_wake")
        _logger.info("Waiting for wake word")

        # Optional hybrid path (Alexa/Jarvis models). Default is Zara-only STT wake.
        if self.wake_detector.has_streaming and self._vad.audio is not None:
            woke = self._listen_hybrid_wake()
            if woke:
                return True
            # Hybrid loop only returns False on mic errors; fall through to classic capture.

        return self._listen_stt_wake()

    def _listen_hybrid_wake(self) -> bool:
        """Listen with openwakeword + STT phrase match for 'Hey Zara'."""
        self.state.transition(AssistantState.LISTENING, reason="hybrid_wake_listen")
        _logger.info("Listening for wake word — say 'Hey Zara'")
        speech_chunks: List[np.ndarray] = []
        in_speech = False
        silence_sec = 0.0
        frame_sec = self.config.voice.frame_duration_sec
        min_samples = int(self.config.voice.sample_rate * self.config.minimum_speech_duration)

        try:
            with self._vad.audio.session():
                while self._running:
                    frame = self._vad.audio.read_frame()

                    if self.wake_detector.check_streaming_frame(frame):
                        return self._acknowledge_wake("streaming_wake", reason="streaming_wake_matched")

                    if self._vad.audio.is_speech(frame):
                        in_speech = True
                        silence_sec = 0.0
                        speech_chunks.append(frame)
                        continue

                    if not in_speech:
                        continue

                    speech_chunks.append(frame)
                    silence_sec += frame_sec
                    if silence_sec < _WAKE_STT_SILENCE_SEC:
                        continue

                    audio = np.concatenate(speech_chunks) if speech_chunks else None
                    speech_chunks = []
                    in_speech = False
                    silence_sec = 0.0

                    if audio is None or audio.size < min_samples:
                        continue

                    self.state.transition(AssistantState.RECORDING, reason="wake_stt_capture")
                    transcript = self._transcribe_safe(audio)
                    if not transcript:
                        self.state.transition(AssistantState.LISTENING, reason="hybrid_wake_listen")
                        continue

                    self.bus.emit(
                        Event(
                            type=EventType.TRANSCRIPT_READY,
                            source="orchestrator",
                            payload={"text": transcript, "phase": "wake"},
                        )
                    )
                    _logger.info("Wake STT heard: %r", transcript)
                    if self.wake_detector.is_wake(transcript):
                        remainder = self.wake_detector.extract_command_after_wake(transcript)
                        if remainder:
                            self._pending_command = remainder
                            _logger.info("Wake included command: %r", remainder)
                        return self._acknowledge_wake(transcript, reason="stt_wake_matched")
                    self.state.transition(AssistantState.LISTENING, reason="hybrid_wake_listen")
        except Exception as exc:
            _logger.warning("Hybrid wake listening error (%s), falling back to VAD+STT", exc)
            return False

        return False

    def _listen_stt_wake(self) -> bool:
        """VAD capture + Whisper match for Zara wake phrases only."""
        self.state.transition(AssistantState.LISTENING, reason="wake_listen")
        _logger.info("Listening for wake word — say 'Hey Zara'")
        capture = self._vad.capture(wait_for_speech=False)
        if not capture.succeeded or capture.audio is None:
            return False

        self.state.transition(AssistantState.RECORDING, reason="wake_capture")
        transcript = self._transcribe_safe(capture.audio)
        if not transcript:
            self.state.reset(reason="empty_wake_transcript")
            return False

        self.bus.emit(
            Event(
                type=EventType.TRANSCRIPT_READY,
                source="orchestrator",
                payload={"text": transcript, "phase": "wake"},
            )
        )

        if not self.wake_detector.is_wake(transcript):
            _logger.info("Wake STT heard (no match): %r", transcript)
            self.state.reset(reason="no_wake_match")
            return False

        remainder = self.wake_detector.extract_command_after_wake(transcript)
        if remainder:
            self._pending_command = remainder
            _logger.info("Wake included command: %r", remainder)
        return self._acknowledge_wake(transcript, reason="wake_matched")

    def _acknowledge_wake(self, text: str, *, reason: str) -> bool:
        self.state.transition(AssistantState.WAKE_DETECTED, reason=reason)
        self.bus.emit(
            Event(
                type=EventType.WAKE_DETECTED,
                source="orchestrator",
                payload={"text": text},
            )
        )
        if self.wake_detector.has_streaming:
            self.wake_detector.reset_streaming()
        # Skip spoken ack when the user already gave a command with the wake phrase.
        if self.config.play_wake_acknowledgement and not self._pending_command:
            self._speak_safe(self.config.wake_acknowledgement_text)
            # Longer pause so TTS/echo is less likely to become an empty command capture.
            delay = float(getattr(self.config, "post_wake_listen_delay_sec", 0.8) or 0.0)
            if delay > 0:
                time.sleep(delay)
        return True

    def _run_command_cycle(self) -> bool:
        """Listen for a command, plan, speak. Returns False to continue outer loop."""
        self.state.transition(AssistantState.LISTENING, reason="await_command")

        if self._pending_command:
            transcript = self._pending_command
            self._pending_command = None
            _logger.info("Using command from wake utterance: %r", transcript)
            self.bus.emit(
                Event(
                    type=EventType.TRANSCRIPT_READY,
                    source="orchestrator",
                    payload={"text": transcript, "phase": "command"},
                )
            )
            if self.wake_detector.is_sleep(transcript):
                self._speak_safe("Going to sleep.")
                return False
            self.session.add_user_turn(transcript)
            return self._think_and_respond(transcript)

        _logger.info("Ready for command")

        capture = self._vad.capture(
            wait_for_speech=True,
            initial_wait_timeout=self.config.wake_timeout,
        )

        if capture.phase is CapturePhase.TIMED_OUT:
            _logger.info("No speech detected within conversation timeout")
            self._speak_safe("I didn't hear anything.")
            return False

        if not capture.succeeded or capture.audio is None:
            return False

        # Ignore tiny blips (often TTS echo) that VAD treats as speech.
        if capture.speech_duration_sec < max(0.45, self.config.minimum_speech_duration):
            _logger.info(
                "Ignoring short command capture (%.2fs speech)",
                capture.speech_duration_sec,
            )
            return True

        self.state.transition(AssistantState.RECORDING, reason="command_capture")

        transcript = self._transcribe_safe(capture.audio)
        if not transcript:
            _logger.warning("STT returned empty transcript; returning to listen")
            self.state.transition(AssistantState.LISTENING, reason="stt_retry")
            self._speak_safe("I didn't catch that. Please try again.")
            # Pause so the retry prompt is not captured as the next utterance.
            time.sleep(float(getattr(self.config, "post_wake_listen_delay_sec", 0.8) or 0.8))
            return True

        self.bus.emit(
            Event(
                type=EventType.TRANSCRIPT_READY,
                source="orchestrator",
                payload={"text": transcript, "phase": "command"},
            )
        )
        _logger.info("User said: %r", transcript)

        if self.wake_detector.is_sleep(transcript):
            self._speak_safe("Going to sleep.")
            return False

        self.session.add_user_turn(transcript)
        return self._think_and_respond(transcript)

    def _think_and_respond(self, transcript: str) -> bool:
        """Planner + tools + TTS. Never raises."""
        self.state.transition(AssistantState.THINKING, reason="planning")
        started = time.monotonic()

        try:
            result = self._planner.plan_and_execute(transcript, self.session)
        except Exception:
            _logger.exception("Planner failed")
            self._speak_safe("Something went wrong.")
            return self._stay_in_conversation_after_response()

        _logger.info("Planner finished in %.2fs", time.monotonic() - started)

        if result.used_tools and result.plan is not None:
            self.state.transition(AssistantState.EXECUTING_TOOL, reason="tools")
            self.bus.emit(
                Event(
                    type=EventType.TOOL_COMPLETED,
                    source="orchestrator",
                    payload={
                        "steps": len(result.plan.steps),
                        "success": result.plan.all_succeeded,
                    },
                )
            )

        self.bus.emit(
            Event(
                type=EventType.RESPONSE_READY,
                source="orchestrator",
                payload={"text": result.spoken_text},
            )
        )

        self.state.transition(AssistantState.SPEAKING, reason="tts")
        self.bus.emit(
            Event(type=EventType.TTS_STARTED, source="orchestrator", payload={})
        )
        interrupted = self._speak_interruptible(result.spoken_text)
        self.bus.emit(
            Event(
                type=EventType.TTS_FINISHED,
                source="orchestrator",
                payload={"interrupted": interrupted},
            )
        )

        self.session.add_assistant_turn(result.spoken_text)
        return self._stay_in_conversation_after_response()

    def _transcribe_safe(self, audio) -> str:
        """Transcribe audio; on failure emit error and return empty string."""
        try:
            text = self._transcriber.transcribe(audio).strip()
            return text
        except Exception as exc:
            _logger.exception("Whisper transcription failed")
            self.bus.emit(
                Event(
                    type=EventType.ERROR,
                    source="stt",
                    payload={"error": str(exc)},
                )
            )
            self.state.transition(AssistantState.ERROR, reason="stt_failure", force=True)
            return ""

    def _speak_safe(self, text: str) -> None:
        if not text:
            return
        try:
            self._speak(text)
        except Exception:
            _logger.exception("TTS failed for text=%r", text)

    def _speak_interruptible(self, text: str) -> bool:
        """Speak while listening for barge-in. Returns True if interrupted."""
        if not text:
            return False
        if (
            not self.config.use_barge_in
            or not self.session.interruptible
            or self._stop_speech is None
            or self._vad.audio is None
        ):
            self._speak_safe(text)
            return False

        done = threading.Event()
        error: list[BaseException] = []

        def _run_tts() -> None:
            try:
                self._speak(text)
            except BaseException as exc:  # noqa: BLE001 - surface to caller thread
                error.append(exc)
            finally:
                done.set()

        worker = threading.Thread(target=_run_tts, name="zara-tts", daemon=True)
        worker.start()

        interrupted = False
        speech_frames = 0
        monitor_started = time.monotonic()
        try:
            with self._vad.audio.session():
                while self._running and not done.is_set():
                    frame = self._vad.audio.read_frame()
                    # Skip early frames — speaker output often echoes into the mic.
                    if time.monotonic() - monitor_started < _BARGE_IN_GRACE_SEC:
                        continue
                    if self._vad.audio.is_speech(frame):
                        speech_frames += 1
                    else:
                        speech_frames = 0
                    if speech_frames >= _BARGE_IN_SPEECH_FRAMES:
                        _logger.info("Barge-in detected — stopping TTS")
                        try:
                            self._stop_speech()
                        except Exception:
                            _logger.exception("Failed to stop speech on barge-in")
                        interrupted = True
                        break
        except Exception:
            _logger.exception("Barge-in monitor failed; waiting for TTS to finish")

        done.wait(timeout=120.0)
        if error:
            _logger.error("TTS failed during interruptible speak: %s", error[0])
        return interrupted

    def _stay_in_conversation_after_response(self) -> bool:
        """Keep the session open for follow-up commands, or end if configured."""
        if self.session.continuous_mode:
            self.state.transition(AssistantState.LISTENING, reason="await_followup")
            _logger.info("Ready for follow-up (no wake word needed)")
            return True
        self._end_conversation()
        return False

    def _end_conversation(self) -> None:
        """Leave the multi-turn session and return to wake-word listening."""
        self.state.reset(reason="conversation_ended")
        _logger.info("Conversation ended — waiting for wake word")

    def _recover_from_error(self) -> None:
        self.state.transition(AssistantState.ERROR, reason="unhandled", force=True)
        self._speak_safe("Something went wrong. I'll keep listening.")
        self.state.reset(reason="recovered")
