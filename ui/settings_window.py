"""Zara main window: voice status + Provider / Intent / Profile tabs."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from agent import get_active_connection_summary
from core.state_manager import AssistantState
from memory.store import get_name, get_preferences, remember_name, set_preference
from ui.intent_panel import IntentPanel
from ui.provider_panel import ProviderPanel
from ui.visualizer import VoiceVisualizerWidget

STATE_LABELS = {
    AssistantState.IDLE: ("IDLE", "#00d2ff"),
    AssistantState.LISTENING: ("LISTENING...", "#00e5ff"),
    AssistantState.RECORDING: ("RECORDING...", "#00e5ff"),
    AssistantState.WAKE_DETECTED: ("WAKE DETECTED", "#00e5ff"),
    AssistantState.THINKING: ("THINKING...", "#b400ff"),
    AssistantState.EXECUTING_TOOL: ("EXECUTING...", "#b400ff"),
    AssistantState.SPEAKING: ("SPEAKING...", "#00ffaa"),
    AssistantState.ERROR: ("ERROR", "#ff3c3c"),
}


class SettingsWindow(QWidget):
    """Main Zara window with voice status and settings tabs."""

    settings_saved = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Zara")
        self.setMinimumSize(920, 620)
        self.resize(1020, 700)
        self._current_state = AssistantState.IDLE
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.WindowCloseButtonHint
            | Qt.WindowType.WindowMinimizeButtonHint
        )
        self.setStyleSheet(
            """
            QWidget {
                background-color: #10141c;
                color: rgba(255, 255, 255, 0.9);
                font-family: "Segoe UI";
            }
            QTabWidget::pane {
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 12px;
                background: rgba(18, 22, 32, 0.95);
                top: -1px;
            }
            QTabBar::tab {
                background: rgba(255, 255, 255, 0.04);
                color: rgba(255, 255, 255, 0.65);
                padding: 10px 18px;
                margin-right: 4px;
                border-top-left-radius: 10px;
                border-top-right-radius: 10px;
                font-weight: 600;
            }
            QTabBar::tab:selected {
                background: rgba(0, 210, 255, 0.16);
                color: #00d2ff;
            }
            QLineEdit, QComboBox, QTextEdit {
                background: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 8px;
                padding: 8px 10px;
                selection-background-color: rgba(0, 210, 255, 0.35);
            }
            QLineEdit:focus, QComboBox:focus, QTextEdit:focus {
                border: 1px solid rgba(0, 210, 255, 0.55);
            }
            QPushButton#primaryBtn {
                background: #00d2ff;
                color: #061018;
                border: none;
                border-radius: 8px;
                padding: 10px 18px;
                font-weight: 700;
            }
            QPushButton#primaryBtn:hover {
                background: #33dbff;
            }
            QPushButton#ghostBtn {
                background: transparent;
                color: rgba(255, 255, 255, 0.7);
                border: 1px solid rgba(255, 255, 255, 0.14);
                border-radius: 8px;
                padding: 10px 16px;
            }
            QLabel#hint {
                color: rgba(255, 255, 255, 0.45);
                font-size: 11px;
            }
            QLabel#sectionTitle {
                color: rgba(255, 255, 255, 0.92);
                font-size: 16px;
                font-weight: 700;
            }
            QCheckBox {
                color: rgba(255, 255, 255, 0.78);
                spacing: 8px;
            }
            """
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 18, 22, 18)
        root.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel("ZARA")
        title.setObjectName("sectionTitle")
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        header.addWidget(title)

        self.state_badge = QLabel("IDLE")
        self.state_badge.setStyleSheet(
            """
            QLabel {
                background-color: rgba(0, 210, 255, 0.18);
                color: #00d2ff;
                border-radius: 8px;
                padding: 4px 10px;
                font-size: 10px;
                font-weight: bold;
            }
            """
        )
        header.addWidget(self.state_badge)
        header.addStretch()
        self.active_model_label = QLabel("")
        self.active_model_label.setObjectName("hint")
        header.addWidget(self.active_model_label)
        root.addLayout(header)

        voice_row = QHBoxLayout()
        self.visualizer = VoiceVisualizerWidget(self)
        self.visualizer.setMinimumHeight(52)
        voice_row.addWidget(self.visualizer, stretch=0)

        self.subtitle_label = QLabel('Say "Hey Zara" to start...')
        self.subtitle_label.setObjectName("hint")
        self.subtitle_label.setWordWrap(True)
        self.subtitle_label.setAlignment(
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
        )
        voice_row.addWidget(self.subtitle_label, stretch=1)
        root.addLayout(voice_row)

        self.tabs = QTabWidget(self)
        self.provider_panel = ProviderPanel(self)
        self.provider_panel.connection_saved.connect(self._on_settings_saved)
        self.intent_panel = IntentPanel(self)
        self.intent_panel.connection_saved.connect(self._on_settings_saved)
        self.tabs.addTab(self.provider_panel, "Provider")
        self.tabs.addTab(self.intent_panel, "Intent")
        self.tabs.addTab(self._build_profile_tab(), "Profile")
        root.addWidget(self.tabs)

        # Back-compat alias used by older call sites / tests.
        self.llm_panel = self.provider_panel
        self.reload_from_disk()

    def set_state(self, state: AssistantState) -> None:
        """Update voice state badge and visualizer."""
        self._current_state = state
        self.visualizer.set_state(state)
        text, color = STATE_LABELS.get(state, (state.value.upper(), "#00d2ff"))
        qcolor = QColor(color)
        self.state_badge.setText(text)
        self.state_badge.setStyleSheet(
            f"""
            QLabel {{
                background-color: rgba({qcolor.red()}, {qcolor.green()}, {qcolor.blue()}, 0.2);
                color: {color};
                border-radius: 8px;
                padding: 4px 10px;
                font-size: 10px;
                font-weight: bold;
            }}
            """
        )

    def set_subtitle(self, text: str) -> None:
        """Show live transcript or assistant reply."""
        self.subtitle_label.setText(text if text else "...")

    def _build_profile_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        intro = QLabel(
            "Tell Zara who you are. This is stored in local memory and used in replies."
        )
        intro.setObjectName("hint")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        form = QFormLayout()
        form.setSpacing(12)

        self.profile_name = QLineEdit()
        self.profile_name.setPlaceholderText("Your name")

        self.preferred_browser = QLineEdit()
        self.preferred_browser.setPlaceholderText("e.g. chrome, edge")

        self.notes_field = QTextEdit()
        self.notes_field.setPlaceholderText("Optional notes or preferences Zara should remember")
        self.notes_field.setFixedHeight(110)

        form.addRow("Name", self.profile_name)
        form.addRow("Preferred browser", self.preferred_browser)
        form.addRow("Notes", self.notes_field)
        layout.addLayout(form)

        actions = QHBoxLayout()
        actions.addStretch()
        refresh_btn = QPushButton("Refresh")
        refresh_btn.setObjectName("ghostBtn")
        refresh_btn.clicked.connect(self._load_profile)
        save_btn = QPushButton("Save profile")
        save_btn.setObjectName("primaryBtn")
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.clicked.connect(self._save_profile)
        actions.addWidget(refresh_btn)
        actions.addWidget(save_btn)
        layout.addLayout(actions)
        layout.addStretch()
        return page

    def reload_from_disk(self) -> None:
        self.provider_panel.reload_from_disk()
        self.intent_panel.reload_from_disk()
        self.active_model_label.setText(get_active_connection_summary())
        self._load_profile()

    def _on_settings_saved(self) -> None:
        self.active_model_label.setText(get_active_connection_summary())
        self.settings_saved.emit()

    def _load_profile(self) -> None:
        self.profile_name.setText(get_name() or "")
        prefs = get_preferences() or {}
        self.preferred_browser.setText(str(prefs.get("browser", "") or ""))
        notes = prefs.get("profile_notes", "")
        self.notes_field.setPlainText(str(notes or ""))

    def _save_profile(self) -> None:
        name = self.profile_name.text().strip()
        browser = self.preferred_browser.text().strip()
        notes = self.notes_field.toPlainText().strip()

        if name:
            remember_name(name)
        if browser:
            set_preference("browser", browser)
        set_preference("profile_notes", notes)

        self.settings_saved.emit()
        QMessageBox.information(self, "Saved", "Profile saved to local memory.")

    def closeEvent(self, event) -> None:  # noqa: N802
        event.ignore()
        self.hide()
        self.visualizer.stop()

    def showEvent(self, event) -> None:  # noqa: N802
        self.reload_from_disk()
        super().showEvent(event)
