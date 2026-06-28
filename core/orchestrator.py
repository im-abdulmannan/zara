"""Event-driven voice assistant orchestrator."""
from __future__ import annotations

import time
from typing import Callable, Optional

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
        planner: Planner | None = None,
        transcriber: WhisperTranscriber | None = None,
        bus: EventBus | None = None,
        session: Session | None = None,
    ) -> None:
        self.config = config
        self._speak = speak
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
        )
        self._vad = VadListener(
            config=config.voice,
            bus=self.bus,
            minimum_speech_duration=config.minimum_speech_duration,
        )
        self._running = False
        self._wire_logging_handlers()

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

        self.state.transition(AssistantState.LISTENING, reason="wake_listen")
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
            self.state.reset(reason="no_wake_match")
            return False

        self.state.transition(AssistantState.WAKE_DETECTED, reason="wake_matched")
        self.bus.emit(
            Event(
                type=EventType.WAKE_DETECTED,
                source="orchestrator",
                payload={"text": transcript},
            )
        )

        if self.config.play_wake_acknowledgement:
            self._speak_safe(self.config.wake_acknowledgement_text)

        return True

    def _run_command_cycle(self) -> bool:
        """Listen for a command, plan, speak. Returns False to continue outer loop."""
        self.state.transition(AssistantState.LISTENING, reason="await_command")
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

        self.state.transition(AssistantState.RECORDING, reason="command_capture")

        transcript = self._transcribe_safe(capture.audio)
        if not transcript:
            _logger.warning("STT returned empty transcript; returning to listen")
            self.state.transition(AssistantState.LISTENING, reason="stt_retry")
            self._speak_safe("I didn't catch that. Please try again.")
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
        self._speak_safe(result.spoken_text)
        self.bus.emit(
            Event(type=EventType.TTS_FINISHED, source="orchestrator", payload={})
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

    def _stay_in_conversation_after_response(self) -> bool:
        """Keep the session open for follow-up commands, or end if configured."""
        if self.config.continuous_conversation:
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
