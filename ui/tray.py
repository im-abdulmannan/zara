"""System Tray Manager for Zara voice assistant."""
from __future__ import annotations

from typing import Callable, Optional
from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QAction, QColor, QIcon, QImage, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from core.state_manager import AssistantState


class SystemTrayManager(QObject):
    """System Tray icon with state updates and context menu controls."""

    toggle_overlay_signal = Signal()
    toggle_continuous_signal = Signal()
    open_settings_signal = Signal()
    quit_signal = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)

        self._icon = QSystemTrayIcon(self)
        self._set_procedural_icon(QColor(0, 210, 255))

        self.menu = QMenu()
        self._init_menu()

        self._icon.setContextMenu(self.menu)
        self._icon.setToolTip("Zara Voice Assistant")
        self._icon.activated.connect(self._on_tray_activated)
        self._icon.show()

    def _set_procedural_icon(self, color: QColor) -> None:
        """Create a clean 32x32 glowing circle icon for system tray."""
        pixmap = QPixmap(32, 32)
        pixmap.fill(QColor(0, 0, 0, 0))

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Outer glow ring
        painter.setPen(QColor(color.red(), color.green(), color.blue(), 100))
        painter.drawEllipse(2, 2, 28, 28)

        # Solid inner dot
        painter.setPen(QColor(0, 0, 0, 0))
        painter.setBrush(color)
        painter.drawEllipse(8, 8, 16, 16)
        painter.end()

        self._icon.setIcon(QIcon(pixmap))

    def _init_menu(self) -> None:
        self.status_action = QAction("Status: Idle", self.menu)
        self.status_action.setEnabled(False)
        self.menu.addAction(self.status_action)

        self.menu.addSeparator()

        self.settings_action = QAction("Open Zara UI", self.menu)
        self.settings_action.triggered.connect(self.open_settings_signal.emit)
        self.menu.addAction(self.settings_action)

        self.continuous_action = QAction("Continuous Mode: ON", self.menu)
        self.continuous_action.setCheckable(True)
        self.continuous_action.setChecked(True)
        self.continuous_action.triggered.connect(self.toggle_continuous_signal.emit)
        self.menu.addAction(self.continuous_action)

        self.menu.addSeparator()

        self.quit_action = QAction("Exit Zara", self.menu)
        self.quit_action.triggered.connect(self.quit_signal.emit)
        self.menu.addAction(self.quit_action)

    def set_state(self, state: AssistantState) -> None:
        """Update system tray icon and tooltip based on state."""
        state_colors = {
            AssistantState.IDLE: QColor(0, 210, 255),
            AssistantState.LISTENING: QColor(0, 229, 255),
            AssistantState.RECORDING: QColor(0, 229, 255),
            AssistantState.WAKE_DETECTED: QColor(0, 229, 255),
            AssistantState.THINKING: QColor(180, 0, 255),
            AssistantState.EXECUTING_TOOL: QColor(180, 0, 255),
            AssistantState.SPEAKING: QColor(0, 255, 170),
            AssistantState.ERROR: QColor(255, 60, 60),
        }
        color = state_colors.get(state, QColor(0, 210, 255))
        self._set_procedural_icon(color)
        self.status_action.setText(f"Status: {state.value.capitalize()}")
        self._icon.setToolTip(f"Zara AI — {state.value.capitalize()}")

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick):
            self.open_settings_signal.emit()
