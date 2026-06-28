"""Voice pipeline: VAD listening, STT, and session orchestration."""

from voice.audio_manager import AudioManager
from voice.config import DEFAULT_LISTENING_CONFIG, ListeningConfig
from voice.listener import (
    RecordingPhase,
    RecordingResult,
    UtteranceRecorder,
    record_utterance,
)
from voice.session import SessionPhase, VoiceSession, VoiceTurn
from voice.stt import WhisperTranscriber, listen, transcribe
from voice.vad_listener import CapturePhase, CaptureResult, VadListener
from voice.wake_word import WakeWordDetector

__all__ = [
    "AudioManager",
    "CapturePhase",
    "CaptureResult",
    "DEFAULT_LISTENING_CONFIG",
    "ListeningConfig",
    "RecordingPhase",
    "RecordingResult",
    "SessionPhase",
    "UtteranceRecorder",
    "VadListener",
    "VoiceSession",
    "VoiceTurn",
    "WakeWordDetector",
    "WhisperTranscriber",
    "listen",
    "record_utterance",
    "transcribe",
]
