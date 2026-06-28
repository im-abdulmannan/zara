"""Zara voice assistant entry point."""
from __future__ import annotations

from config import WAKE_WORD
from core.config import AssistantConfig
from core.logging_config import get_logger
from core.orchestrator import VoiceOrchestrator
from runtime import get_runtime, shutdown_runtime

_logger = get_logger(__name__)


def main() -> None:
    runtime = get_runtime()
    config = AssistantConfig.from_env(wake_word=WAKE_WORD)

    runtime.speak("Hello, I am Zara.")

    orchestrator = VoiceOrchestrator(
        config=config,
        speak=runtime.speak,
    )

    try:
        orchestrator.run()
    except KeyboardInterrupt:
        _logger.info("Shutting down Zara...")
    finally:
        shutdown_runtime()


if __name__ == "__main__":
    main()
