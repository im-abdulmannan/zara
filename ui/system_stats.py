"""Live CPU and memory usage panel for the settings window."""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

try:
    import psutil

    HAS_PSUTIL = True
except ImportError:  # pragma: no cover - optional at import time
    HAS_PSUTIL = False


class _UsageBar(QWidget):
    """Simple horizontal usage bar (0-100)."""

    def __init__(self, color: str = "#00d2ff", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._value = 0.0
        self._color = QColor(color)
        self.setFixedHeight(10)

    def set_value(self, value: float) -> None:
        self._value = max(0.0, min(100.0, float(value)))
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(0, 1, 0, -1)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(255, 255, 255, 28))
        painter.drawRoundedRect(rect, 4, 4)

        fill_width = int(rect.width() * (self._value / 100.0))
        if fill_width > 0:
            fill = rect.adjusted(0, 0, -(rect.width() - fill_width), 0)
            painter.setBrush(self._color)
            painter.drawRoundedRect(fill, 4, 4)

        painter.setPen(QPen(QColor(255, 255, 255, 40), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(rect, 4, 4)


class SystemStatsPanel(QFrame):
    """Left-side panel showing live CPU and RAM usage."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("statsPanel")
        self.setFixedWidth(170)
        self.setStyleSheet(
            """
            QFrame#statsPanel {
                background-color: rgba(10, 14, 22, 0.92);
                border-right: 1px solid rgba(255, 255, 255, 0.08);
            }
            QLabel#statsTitle {
                color: rgba(255, 255, 255, 0.55);
                font-size: 10px;
                font-weight: 700;
                letter-spacing: 1.2px;
            }
            QLabel#metricName {
                color: rgba(255, 255, 255, 0.78);
                font-size: 12px;
                font-weight: 600;
            }
            QLabel#metricValue {
                color: #00d2ff;
                font-size: 22px;
                font-weight: 700;
            }
            QLabel#metricDetail {
                color: rgba(255, 255, 255, 0.45);
                font-size: 10px;
            }
            """
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 20, 16, 20)
        layout.setSpacing(18)

        title = QLabel("SYSTEM")
        title.setObjectName("statsTitle")
        title.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        layout.addWidget(title)

        self.cpu_name = QLabel("CPU")
        self.cpu_name.setObjectName("metricName")
        self.cpu_value = QLabel("--%")
        self.cpu_value.setObjectName("metricValue")
        self.cpu_bar = _UsageBar("#00d2ff")
        self.cpu_detail = QLabel("Processor load")
        self.cpu_detail.setObjectName("metricDetail")
        self.cpu_detail.setWordWrap(True)

        layout.addWidget(self.cpu_name)
        layout.addWidget(self.cpu_value)
        layout.addWidget(self.cpu_bar)
        layout.addWidget(self.cpu_detail)

        layout.addSpacing(8)

        self.mem_name = QLabel("MEMORY")
        self.mem_name.setObjectName("metricName")
        self.mem_value = QLabel("--%")
        self.mem_value.setObjectName("metricValue")
        self.mem_value.setStyleSheet("color: #00ffaa;")
        self.mem_bar = _UsageBar("#00ffaa")
        self.mem_detail = QLabel("RAM in use")
        self.mem_detail.setObjectName("metricDetail")
        self.mem_detail.setWordWrap(True)

        layout.addWidget(self.mem_name)
        layout.addWidget(self.mem_value)
        layout.addWidget(self.mem_bar)
        layout.addWidget(self.mem_detail)
        layout.addStretch()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh)
        self._timer.start(1000)
        # Prime CPU percent baseline.
        if HAS_PSUTIL:
            psutil.cpu_percent(interval=None)
        self.refresh()

    def refresh(self) -> None:
        if not HAS_PSUTIL:
            self.cpu_value.setText("n/a")
            self.mem_value.setText("n/a")
            self.cpu_detail.setText("Install psutil for live stats")
            self.mem_detail.setText("")
            return

        cpu = float(psutil.cpu_percent(interval=None))
        memory = psutil.virtual_memory()
        mem_percent = float(memory.percent)
        used_gb = memory.used / (1024**3)
        total_gb = memory.total / (1024**3)

        self.cpu_value.setText(f"{cpu:.0f}%")
        self.cpu_bar.set_value(cpu)
        self.cpu_detail.setText(f"{psutil.cpu_count(logical=True) or '?'} logical cores")

        self.mem_value.setText(f"{mem_percent:.0f}%")
        self.mem_bar.set_value(mem_percent)
        self.mem_detail.setText(f"{used_gb:.1f} / {total_gb:.1f} GB")

    def start(self) -> None:
        if not self._timer.isActive():
            self._timer.start(1000)
        self.refresh()

    def stop(self) -> None:
        if self._timer.isActive():
            self._timer.stop()
