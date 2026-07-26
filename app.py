import signal
import sys
import threading
import webbrowser

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from api.server import start_api_server, ui_url
from api.status_store import update_status
from config import WAKE_WORD
from core.config import AssistantConfig
from core.event_bus import Event, EventBus, EventType
from core.logging_config import get_logger
from core.orchestrator import VoiceOrchestrator
from core.state_manager import AssistantState
from runtime import get_runtime, shutdown_runtime
from ui import SystemTrayManager, UIEventBridge

_logger = get_logger(__name__)

UI_HOST = "127.0.0.1"
UI_PORT = 8787


def main() -> None:
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    runtime = get_runtime()
    config = AssistantConfig.from_env(wake_word=WAKE_WORD)

    bus = EventBus()
    orchestrator = VoiceOrchestrator(
        config=config,
        speak=runtime.speak,
        stop_speech=runtime.speaker.stop,
        bus=bus,
    )

    from agent import get_active_connection_summary

    update_status(
        state="idle",
        subtitle='Say "Hey Zara" to start...',
        active_model=get_active_connection_summary(),
    )

    start_api_server(host=UI_HOST, port=UI_PORT)
    url = ui_url(UI_HOST, UI_PORT)
    _logger.info("React UI available at %s", url)

    tray = SystemTrayManager()
    tray.continuous_action.setChecked(config.continuous_conversation)
    tray.continuous_action.setText(
        f"Continuous Mode: {'ON' if config.continuous_conversation else 'OFF'}"
    )
    tray.settings_action.setText("Open Zara UI")

    bridge = UIEventBridge(bus)
    bridge.state_changed_signal.connect(
        lambda state: update_status(state=getattr(state, "value", str(state)))
    )
    bridge.state_changed_signal.connect(tray.set_state)
    bridge.transcript_signal.connect(lambda text: update_status(subtitle=text))
    bridge.response_signal.connect(lambda text: update_status(subtitle=text))
    bridge.error_signal.connect(lambda text: update_status(subtitle=text))

    shutting_down = False

    def _show_ui() -> None:
        webbrowser.open(url)

    def _toggle_continuous() -> None:
        enabled = tray.continuous_action.isChecked()
        orchestrator.set_continuous_mode(enabled)
        tray.continuous_action.setText(
            f"Continuous Mode: {'ON' if enabled else 'OFF'}"
        )
        try:
            from ui.env_settings import upsert_env_values

            upsert_env_values(
                {"CONTINUOUS_CONVERSATION": "true" if enabled else "false"}
            )
        except Exception as exc:
            _logger.warning("Failed to persist continuous mode: %s", exc)
        _logger.info("Continuous mode toggled via tray: %s", enabled)

    def _quit_zara(*_args) -> None:
        nonlocal shutting_down
        if shutting_down:
            return
        shutting_down = True
        _logger.info("Quitting Zara...")
        orchestrator.stop()
        try:
            runtime.speaker.stop()
        except Exception:
            pass
        shutdown_runtime()
        tray._icon.hide()
        app.quit()

    tray.open_settings_signal.connect(_show_ui)
    tray.toggle_continuous_signal.connect(_toggle_continuous)
    tray.quit_signal.connect(_quit_zara)

    signal.signal(signal.SIGINT, _quit_zara)
    signal_timer = QTimer()
    signal_timer.start(200)
    signal_timer.timeout.connect(lambda: None)

    # Seed status from bus events that may not go through bridge helpers.
    def _on_bus(event: Event) -> None:
        if event.type is EventType.STATE_CHANGED:
            to_state = event.payload.get("to")
            if isinstance(to_state, AssistantState):
                update_status(state=to_state.value)
            elif to_state is not None:
                update_status(state=str(to_state))

    bus.subscribe(EventType.STATE_CHANGED, _on_bus)

    QTimer.singleShot(400, _show_ui)
    runtime.speak("Hello, I am Zara.")

    orchestrator_thread = threading.Thread(target=orchestrator.run, daemon=True)
    orchestrator_thread.start()

    try:
        sys.exit(app.exec())
    except KeyboardInterrupt:
        _quit_zara()
    finally:
        if not shutting_down:
            _quit_zara()


if __name__ == "__main__":
    main()
