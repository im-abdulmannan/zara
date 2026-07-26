"""Custom animated dynamic audio visualizer widget for PySide6."""
from __future__ import annotations

import math
from PySide6.QtCore import QPointF, QRectF, QTimer, Qt
from PySide6.QtGui import QColor, QConicalGradient, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

from core.state_manager import AssistantState


class VoiceVisualizerWidget(QWidget):
    """Dynamic 60FPS animated voice visualizer reacting to assistant state."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(140, 48)

        self._state: AssistantState = AssistantState.IDLE
        self._phase: float = 0.0
        self._angle: float = 0.0

        # 60 FPS animation timer (~16ms interval)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_tick)
        self._timer.start(16)

    def set_state(self, state: AssistantState) -> None:
        """Update active visual state."""
        self._state = state
        self.update()

    def start(self) -> None:
        """Resume the animation timer."""
        if not self._timer.isActive():
            self._timer.start(16)

    def stop(self) -> None:
        """Stop the animation timer (call on app shutdown)."""
        if self._timer.isActive():
            self._timer.stop()

    def _on_tick(self) -> None:
        try:
            self._phase += 0.08
            if self._phase > 2 * math.pi:
                self._phase -= 2 * math.pi

            self._angle = (self._angle + 3.0) % 360.0
            self.update()
        except KeyboardInterrupt:
            self.stop()
            raise

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect()
        width = rect.width()
        height = rect.height()
        cy = height / 2.0

        if self._state in (AssistantState.IDLE, AssistantState.ERROR):
            # Calm breathing pulse dot
            pulse = (math.sin(self._phase) + 1.0) / 2.0
            radius = 8 + pulse * 4
            color = QColor(0, 210, 255, int(150 + pulse * 105)) if self._state == AssistantState.IDLE else QColor(255, 60, 60, 220)
            
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)
            painter.drawEllipse(QPointF(width / 2.0, cy), radius, radius)

        elif self._state in (AssistantState.LISTENING, AssistantState.RECORDING, AssistantState.WAKE_DETECTED):
            # Glowing animated audio wave bars (Cyan / Electric Blue)
            num_bars = 7
            bar_width = 4.0
            gap = 6.0
            total_width = num_bars * bar_width + (num_bars - 1) * gap
            start_x = (width - total_width) / 2.0

            for i in range(num_bars):
                # Calculate wave amplitude based on sine phase and bar position
                amp = math.sin(self._phase * 1.5 + i * 0.6)
                bar_h = 10 + (abs(amp) * (height * 0.6))
                x = start_x + i * (bar_width + gap)
                y = cy - bar_h / 2.0

                gradient = QLinearGradient(x, y, x, y + bar_h)
                gradient.setColorAt(0.0, QColor(0, 229, 255, 240))
                gradient.setColorAt(1.0, QColor(0, 140, 255, 200))

                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(gradient)
                painter.drawRoundedRect(QRectF(x, y, bar_width, bar_h), 2, 2)

        elif self._state in (AssistantState.THINKING, AssistantState.EXECUTING_TOOL):
            # Spinning glowing ring (Purple / Magenta)
            center = QPointF(width / 2.0, cy)
            r = 16.0

            gradient = QConicalGradient(center, self._angle)
            gradient.setColorAt(0.0, QColor(180, 0, 255, 240))
            gradient.setColorAt(0.5, QColor(255, 0, 180, 180))
            gradient.setColorAt(1.0, QColor(180, 0, 255, 20))

            pen = QPen(gradient, 4.0)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawArc(QRectF(center.x() - r, center.y() - r, r * 2, r * 2), 0, 280 * 16)

        elif self._state == AssistantState.SPEAKING:
            # Active speech spectrum wave (Emerald / Spring Green)
            num_bars = 9
            bar_width = 3.5
            gap = 4.5
            total_width = num_bars * bar_width + (num_bars - 1) * gap
            start_x = (width - total_width) / 2.0

            for i in range(num_bars):
                amp = math.sin(self._phase * 2.2 + i * 0.8) * math.cos(self._phase * 0.9 + i)
                bar_h = 8 + (abs(amp) * (height * 0.7))
                x = start_x + i * (bar_width + gap)
                y = cy - bar_h / 2.0

                gradient = QLinearGradient(x, y, x, y + bar_h)
                gradient.setColorAt(0.0, QColor(0, 255, 170, 240))
                gradient.setColorAt(1.0, QColor(0, 200, 110, 200))

                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(gradient)
                painter.drawRoundedRect(QRectF(x, y, bar_width, bar_h), 2, 2)
