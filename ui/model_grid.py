"""Selectable model cards in a scrollable grid."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from core.llm_config import is_free_model


class ModelCard(QFrame):
    """Clickable card representing one model ID."""

    clicked = Signal(str)

    def __init__(self, model_id: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.model_id = model_id
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(78)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)

        title = QLabel(model_id)
        title.setWordWrap(True)
        title.setStyleSheet("font-weight: 700; font-size: 12px;")
        layout.addWidget(title)

        badge = "FREE" if is_free_model(model_id) else "MODEL"
        meta = QLabel(badge)
        meta.setObjectName("hint")
        meta.setStyleSheet(
            "font-size: 10px; font-weight: 700; color: #7dffa8;"
            if is_free_model(model_id)
            else "font-size: 10px; color: rgba(255,255,255,0.45);"
        )
        layout.addWidget(meta)
        self.set_selected(False)

    def set_selected(self, selected: bool) -> None:
        if selected:
            self.setStyleSheet(
                """
                QFrame {
                    background: rgba(0, 210, 255, 0.16);
                    border: 1px solid rgba(0, 210, 255, 0.7);
                    border-radius: 12px;
                }
                """
            )
        else:
            self.setStyleSheet(
                """
                QFrame {
                    background: rgba(255, 255, 255, 0.04);
                    border: 1px solid rgba(255, 255, 255, 0.1);
                    border-radius: 12px;
                }
                QFrame:hover {
                    border: 1px solid rgba(0, 210, 255, 0.45);
                    background: rgba(255, 255, 255, 0.06);
                }
                """
            )

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.model_id)
        super().mousePressEvent(event)


class ModelGrid(QWidget):
    """Grid of model cards with optional free-only filtering."""

    model_selected = Signal(str)

    def __init__(self, parent: QWidget | None = None, columns: int = 2) -> None:
        super().__init__(parent)
        self._columns = max(1, columns)
        self._all_models: list[str] = []
        self._selected = ""
        self._free_only = False
        self._cards: list[ModelCard] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        self.empty_label = QLabel("No models to show. Fetch models or adjust the free filter.")
        self.empty_label.setObjectName("hint")
        self.empty_label.setWordWrap(True)
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self.empty_label)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        root.addWidget(self.scroll, stretch=1)

        self.grid_host = QWidget()
        self.grid = QGridLayout(self.grid_host)
        self.grid.setContentsMargins(0, 0, 8, 0)
        self.grid.setHorizontalSpacing(10)
        self.grid.setVerticalSpacing(10)
        self.grid.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll.setWidget(self.grid_host)

    @property
    def selected_model(self) -> str:
        return self._selected

    def set_free_only(self, enabled: bool) -> None:
        self._free_only = bool(enabled)
        self._rebuild()

    def set_models(self, models: list[str], selected: str | None = None) -> None:
        seen: set[str] = set()
        ordered: list[str] = []
        for model in models:
            mid = str(model).strip()
            if mid and mid not in seen:
                seen.add(mid)
                ordered.append(mid)
        self._all_models = ordered
        if selected is not None:
            self._selected = selected.strip()
        if self._selected and self._selected not in self._all_models:
            self._all_models.insert(0, self._selected)
        self._rebuild()

    def select_model(self, model_id: str) -> None:
        self._selected = (model_id or "").strip()
        for card in self._cards:
            card.set_selected(card.model_id == self._selected)

    def _visible_models(self) -> list[str]:
        if not self._free_only:
            return list(self._all_models)
        return [m for m in self._all_models if is_free_model(m)]

    def _rebuild(self) -> None:
        while self.grid.count():
            item = self.grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._cards.clear()

        models = self._visible_models()
        self.empty_label.setVisible(not models)
        self.scroll.setVisible(bool(models))
        if not models:
            return

        for index, model_id in enumerate(models):
            card = ModelCard(model_id, self.grid_host)
            card.set_selected(model_id == self._selected)
            card.clicked.connect(self._on_card_clicked)
            row, col = divmod(index, self._columns)
            self.grid.addWidget(card, row, col)
            self._cards.append(card)

    def _on_card_clicked(self, model_id: str) -> None:
        self.select_model(model_id)
        self.model_selected.emit(model_id)
