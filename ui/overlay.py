"""Glassmorphic Floating Voice Overlay Widget for Windows."""
from __future__ import annotations

from PySide6.QtCore import QPoint, QPropertyAnimation, QRect, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QMouseEvent
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.state_manager import AssistantState
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


class FloatingVoiceOverlay(QWidget):
    """Frameless, translucent floating voice overlay that stays on top."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        # Window flags: Frameless, Always on Top, Tool window (no taskbar clutter)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        self._drag_position = QPoint()
        self._current_state = AssistantState.IDLE

        self._init_ui()
        self._position_on_screen()

    def _init_ui(self) -> None:
        # Container frame for glassmorphic styling
        self.container = QFrame(self)
        self.container.setObjectName("container")
        self.container.setStyleSheet("""
            QFrame#container {
                background-color: rgba(18, 20, 30, 0.88);
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 18px;
            }
        """)

        # Main Layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.container)

        # Container Layout
        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(16, 12, 16, 14)
        container_layout.setSpacing(8)

        # Top Header (State Pill + Title + Hide button)
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)

        self.title_label = QLabel("ZARA", self.container)
        title_font = QFont("Segoe UI", 10, QFont.Weight.Bold)
        self.title_label.setFont(title_font)
        self.title_label.setStyleSheet("color: rgba(255, 255, 255, 0.9); font-weight: 700; letter-spacing: 1px;")

        self.state_badge = QLabel("IDLE", self.container)
        self.state_badge.setStyleSheet("""
            QLabel {
                background-color: rgba(0, 210, 255, 0.18);
                color: #00d2ff;
                border-radius: 8px;
                padding: 2px 8px;
                font-size: 9px;
                font-weight: bold;
            }
        """)

        header_layout.addWidget(self.title_label)
        header_layout.addWidget(self.state_badge)
        header_layout.addStretch()

        self.settings_btn = QPushButton("⚙", self.container)
        self.settings_btn.setFixedSize(20, 20)
        self.settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.settings_btn.setToolTip("Open settings")
        self.settings_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: rgba(255, 255, 255, 0.5);
                border: none;
                font-size: 12px;
            }
            QPushButton:hover {
                color: #00d2ff;
            }
        """)
        header_layout.addWidget(self.settings_btn)

        self.close_btn = QPushButton("✕", self.container)
        self.close_btn.setFixedSize(20, 20)
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: rgba(255, 255, 255, 0.5);
                border: none;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                color: #ff5555;
            }
        """)
        self.close_btn.clicked.connect(self.hide)
        header_layout.addWidget(self.close_btn)

        container_layout.addLayout(header_layout)

        # Visualizer Widget
        self.visualizer = VoiceVisualizerWidget(self.container)
        container_layout.addWidget(self.visualizer, alignment=Qt.AlignmentFlag.AlignCenter)

        # Live Transcript / Response Subtitle Label
        self.subtitle_label = QLabel("Say \"Hey Zara\" to start...", self.container)
        self.subtitle_label.setWordWrap(True)
        self.subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.subtitle_label.setStyleSheet("""
            QLabel {
                color: rgba(255, 255, 255, 0.75);
                font-size: 11px;
                font-family: "Segoe UI";
            }
        """)
        container_layout.addWidget(self.subtitle_label)

        self.setFixedSize(300, 130)

    def _position_on_screen(self) -> None:
        """Position window at bottom right of primary monitor."""
        screen = QApplication.primaryScreen()
        if screen is not None:
            geom = screen.availableGeometry()
            x = geom.right() - self.width() - 30
            y = geom.bottom() - self.height() - 40
            self.move(x, y)

    def set_state(self, state: AssistantState) -> None:
        """Update state badge, color, and visualizer animation."""
        self._current_state = state
        self.visualizer.set_state(state)

        text, color = STATE_LABELS.get(state, (state.value.upper(), "#00d2ff"))
        self.state_badge.setText(text)
        self.state_badge.setStyleSheet(f"""
            QLabel {{
                background-color: rgba({QColor(color).red()}, {QColor(color).green()}, {QColor(color).blue()}, 0.2);
                color: {color};
                border-radius: 8px;
                padding: 2px 8px;
                font-size: 9px;
                font-weight: bold;
            }}
        """)

    def set_subtitle(self, text: str) -> None:
        """Set subtitle / transcript preview text."""
        self.subtitle_label.setText(text if text else "...")

    # Mouse Drag Window Implementation
    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.buttons() == Qt.MouseButton.LeftButton and not self._drag_position.isNull():
            self.move(event.globalPosition().toPoint() - self._drag_position)
            event.accept()
