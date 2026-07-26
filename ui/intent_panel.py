"""Intent tab: enable/disable first, then configure and save details."""
from __future__ import annotations

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from agent import apply_llm_connection
from core.llm_config import (
    INTENT_MODEL_CHOICES,
    LlmConnection,
    PROVIDER_PRESETS,
    connection_from_env,
    connection_to_env_updates,
    fetch_remote_models,
    preset_by_id,
)
from ui.env_settings import upsert_env_values
from ui.model_grid import ModelGrid


class _Worker(QThread):
    finished_ok = Signal(object)
    finished_err = Signal(str)

    def __init__(self, fn, parent=None) -> None:
        super().__init__(parent)
        self._fn = fn

    def run(self) -> None:
        try:
            self.finished_ok.emit(self._fn())
        except Exception as exc:  # noqa: BLE001
            self.finished_err.emit(str(exc))


class IntentPanel(QWidget):
    """Ask whether to enable Intent, then allow full configuration + save."""

    connection_saved = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._worker: _Worker | None = None
        self._building = False
        self._selected_model = ""
        self._all_models: list[str] = []
        self._enabled = False

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(14)

        title = QLabel("Intent classification")
        title.setObjectName("sectionTitle")
        root.addWidget(title)

        self.gate_card = QFrame()
        self.gate_card.setObjectName("settingsCard")
        self.gate_card.setStyleSheet(
            """
            QFrame#settingsCard {
                background: rgba(255, 255, 255, 0.03);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 12px;
            }
            """
        )
        gate_layout = QVBoxLayout(self.gate_card)
        gate_layout.setContentsMargins(18, 18, 18, 18)
        gate_layout.setSpacing(12)

        self.gate_question = QLabel(
            "Do you want to enable Intent classification?\n\n"
            "When enabled, Zara quickly routes clear commands (reminders, open apps, "
            "search) before calling the main chat model. You can turn this off anytime."
        )
        self.gate_question.setWordWrap(True)
        gate_layout.addWidget(self.gate_question)

        gate_actions = QHBoxLayout()
        self.enable_btn = QPushButton("Yes, enable Intent")
        self.enable_btn.setObjectName("primaryBtn")
        self.enable_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.enable_btn.clicked.connect(lambda: self._set_enabled(True, persist=True))
        self.disable_btn = QPushButton("No, keep disabled")
        self.disable_btn.setObjectName("ghostBtn")
        self.disable_btn.clicked.connect(lambda: self._set_enabled(False, persist=True))
        gate_actions.addWidget(self.enable_btn)
        gate_actions.addWidget(self.disable_btn)
        gate_actions.addStretch()
        gate_layout.addLayout(gate_actions)
        root.addWidget(self.gate_card)

        self.details = QWidget()
        details_layout = QVBoxLayout(self.details)
        details_layout.setContentsMargins(0, 0, 0, 0)
        details_layout.setSpacing(12)

        status_row = QHBoxLayout()
        self.enabled_badge = QLabel("Intent: ON")
        self.enabled_badge.setStyleSheet(
            """
            QLabel {
                background: rgba(0, 255, 170, 0.16);
                color: #00ffaa;
                border-radius: 8px;
                padding: 6px 12px;
                font-weight: 700;
                font-size: 11px;
            }
            """
        )
        status_row.addWidget(self.enabled_badge)
        status_row.addStretch()
        self.turn_off_btn = QPushButton("Disable Intent")
        self.turn_off_btn.setObjectName("ghostBtn")
        self.turn_off_btn.clicked.connect(lambda: self._set_enabled(False, persist=True))
        status_row.addWidget(self.turn_off_btn)
        details_layout.addLayout(status_row)

        form_card = QFrame()
        form_card.setObjectName("settingsCard")
        form_card.setStyleSheet(self.gate_card.styleSheet())
        form_layout = QFormLayout(form_card)
        form_layout.setContentsMargins(14, 14, 14, 14)
        form_layout.setSpacing(10)

        self.backend_combo = QComboBox()
        self.backend_combo.addItem("Gemini (Google AI)", "gemini")
        self.backend_combo.addItem("Any OpenAI-compatible LLM", "openai")
        self.backend_combo.currentIndexChanged.connect(self._on_backend_changed)

        self.provider_combo = QComboBox()
        for preset in PROVIDER_PRESETS:
            self.provider_combo.addItem(preset.label, preset.id)
        self.provider_combo.currentIndexChanged.connect(self._on_provider_changed)

        self.base_url_input = QLineEdit()
        self.base_url_input.setPlaceholderText("https://openrouter.ai/api/v1")

        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_input.setPlaceholderText("API key")
        key_row = QHBoxLayout()
        key_row.addWidget(self.api_key_input, stretch=1)
        self.show_key_btn = QPushButton("Show")
        self.show_key_btn.setObjectName("ghostBtn")
        self.show_key_btn.setCheckable(True)
        self.show_key_btn.toggled.connect(self._toggle_key_visibility)
        key_row.addWidget(self.show_key_btn)

        self.confidence_spin = QDoubleSpinBox()
        self.confidence_spin.setRange(0.0, 1.0)
        self.confidence_spin.setSingleStep(0.05)
        self.confidence_spin.setDecimals(2)
        self.confidence_spin.setValue(0.70)

        form_layout.addRow("Backend", self.backend_combo)
        form_layout.addRow("Provider", self.provider_combo)
        form_layout.addRow("Base URL", self.base_url_input)
        form_layout.addRow("API key", key_row)
        form_layout.addRow("Confidence", self.confidence_spin)
        self._provider_label = form_layout.labelForField(self.provider_combo)
        self._base_url_label = form_layout.labelForField(self.base_url_input)
        details_layout.addWidget(form_card)

        model_toolbar = QHBoxLayout()
        model_toolbar.addWidget(QLabel("Intent model"))
        model_toolbar.addStretch()
        self.fetch_models_btn = QPushButton("Fetch models")
        self.fetch_models_btn.setObjectName("ghostBtn")
        self.fetch_models_btn.clicked.connect(self._fetch_models)
        model_toolbar.addWidget(self.fetch_models_btn)
        details_layout.addLayout(model_toolbar)

        filter_row = QHBoxLayout()
        self.free_only_check = QCheckBox("Show free models only")
        self.free_only_check.toggled.connect(self._on_free_filter)
        filter_row.addWidget(self.free_only_check)
        filter_row.addStretch()
        details_layout.addLayout(filter_row)

        self.selected_label = QLabel("Selected intent model: —")
        self.selected_label.setObjectName("hint")
        details_layout.addWidget(self.selected_label)

        self.manual_model_input = QLineEdit()
        self.manual_model_input.setPlaceholderText("Or type an intent model ID")
        self.manual_model_input.textEdited.connect(self._on_manual_model)
        details_layout.addWidget(self.manual_model_input)

        self.model_grid = ModelGrid(columns=2)
        self.model_grid.setMinimumHeight(180)
        self.model_grid.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.model_grid.model_selected.connect(self._on_model_selected)
        details_layout.addWidget(self.model_grid, stretch=1)

        self.status_label = QLabel("")
        self.status_label.setObjectName("hint")
        self.status_label.setWordWrap(True)
        details_layout.addWidget(self.status_label)

        save_row = QHBoxLayout()
        save_row.addStretch()
        self.save_btn = QPushButton("Save Intent details")
        self.save_btn.setObjectName("primaryBtn")
        self.save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.save_btn.clicked.connect(self._save_details)
        save_row.addWidget(self.save_btn)
        details_layout.addLayout(save_row)

        root.addWidget(self.details, stretch=1)
        self.reload_from_disk()

    def reload_from_disk(self) -> None:
        self._building = True
        connection = connection_from_env()
        self._enabled = bool(connection.intent_enabled)
        backend_idx = self.backend_combo.findData(connection.intent_backend or "gemini")
        self.backend_combo.setCurrentIndex(max(backend_idx, 0))
        provider_idx = self.provider_combo.findData(connection.intent_provider_id or "openrouter")
        self.provider_combo.setCurrentIndex(max(provider_idx, 0))
        self.base_url_input.setText(connection.intent_base_url or "")
        self.api_key_input.setText(connection.intent_api_key or connection.gemini_api_key or "")
        self.confidence_spin.setValue(float(connection.intent_confidence))
        self._selected_model = connection.intent_model
        self.manual_model_input.setText(connection.intent_model)
        self._sync_models(
            connection.intent_backend or "gemini",
            prefer=connection.intent_model,
            provider_id=connection.intent_provider_id,
        )
        self._building = False
        self._refresh_visibility()
        self._update_status()

    def _set_enabled(self, enabled: bool, *, persist: bool) -> None:
        self._enabled = bool(enabled)
        self._refresh_visibility()
        self._update_status()
        if persist:
            self._save_enabled_only()

    def _refresh_visibility(self) -> None:
        self.gate_card.setVisible(not self._enabled)
        self.details.setVisible(self._enabled)
        backend = str(self.backend_combo.currentData() or "gemini")
        is_openai = backend == "openai"
        self.provider_combo.setVisible(is_openai)
        self.base_url_input.setVisible(is_openai)
        self.fetch_models_btn.setVisible(is_openai)
        if self._provider_label is not None:
            self._provider_label.setVisible(is_openai)
        if self._base_url_label is not None:
            self._base_url_label.setVisible(is_openai)
        if backend == "gemini":
            self.api_key_input.setPlaceholderText("Gemini API key")
        else:
            preset = preset_by_id(str(self.provider_combo.currentData() or "custom"))
            self.api_key_input.setPlaceholderText(
                preset.api_key_placeholder if preset else "API key"
            )

    def _update_status(self) -> None:
        if not self._enabled:
            self.status_label.setText("Intent is disabled. Enable it to configure routing.")
            return
        backend = str(self.backend_combo.currentData() or "gemini")
        if backend == "gemini":
            self.status_label.setText(
                f"Intent: Gemini · {self._selected_model} · "
                f"confidence ≥ {self.confidence_spin.value():.2f}"
            )
        else:
            self.status_label.setText(
                f"Intent: {self.provider_combo.currentData()} · {self._selected_model} · "
                f"confidence ≥ {self.confidence_spin.value():.2f}"
            )

    def _on_backend_changed(self) -> None:
        if self._building:
            return
        backend = str(self.backend_combo.currentData() or "gemini")
        self._sync_models(backend)
        self._refresh_visibility()
        self._update_status()

    def _on_provider_changed(self) -> None:
        if self._building:
            return
        if str(self.backend_combo.currentData() or "") != "openai":
            return
        provider_id = str(self.provider_combo.currentData() or "custom")
        preset = preset_by_id(provider_id)
        if preset is None:
            return
        if preset.base_url:
            self.base_url_input.setText(preset.base_url)
        if preset.default_api_key and not self.api_key_input.text().strip():
            self.api_key_input.setText(preset.default_api_key)
        self.api_key_input.setPlaceholderText(preset.api_key_placeholder)
        self._sync_models("openai", provider_id=provider_id)
        self._update_status()

    def _sync_models(
        self,
        backend: str,
        prefer: str | None = None,
        provider_id: str | None = None,
    ) -> None:
        if backend == "gemini":
            models = list(INTENT_MODEL_CHOICES)
        else:
            preset = preset_by_id(provider_id or str(self.provider_combo.currentData() or ""))
            models = list(preset.models) if preset else []
        selected = (prefer or self._selected_model or "").strip()
        if selected and selected not in models:
            models.insert(0, selected)
        self._all_models = models
        self._selected_model = selected or (models[0] if models else "")
        self.manual_model_input.setText(self._selected_model)
        self.model_grid.set_free_only(self.free_only_check.isChecked())
        self.model_grid.set_models(self._all_models, selected=self._selected_model)
        self.selected_label.setText(f"Selected intent model: {self._selected_model or '—'}")

    def _on_free_filter(self, checked: bool) -> None:
        self.model_grid.set_free_only(checked)
        self.model_grid.set_models(self._all_models, selected=self._selected_model)

    def _on_model_selected(self, model_id: str) -> None:
        self._selected_model = model_id
        self.manual_model_input.setText(model_id)
        self.selected_label.setText(f"Selected intent model: {model_id}")
        self._update_status()

    def _on_manual_model(self, text: str) -> None:
        self._selected_model = text.strip()
        self.model_grid.select_model(self._selected_model)
        self.selected_label.setText(f"Selected intent model: {self._selected_model or '—'}")

    def _toggle_key_visibility(self, checked: bool) -> None:
        mode = QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
        self.api_key_input.setEchoMode(mode)
        self.show_key_btn.setText("Hide" if checked else "Show")

    def _build_connection(self, *, enabled: bool | None = None) -> LlmConnection:
        existing = connection_from_env()
        backend = str(self.backend_combo.currentData() or "gemini")
        key = self.api_key_input.text().strip()
        return LlmConnection(
            provider_id=existing.provider_id,
            label=existing.label,
            base_url=existing.base_url,
            api_key=existing.api_key,
            model=existing.model,
            gemini_api_key=key if backend == "gemini" else existing.gemini_api_key,
            intent_enabled=self._enabled if enabled is None else enabled,
            intent_backend=backend,
            intent_provider_id=str(self.provider_combo.currentData() or "openrouter"),
            intent_base_url=self.base_url_input.text().strip().rstrip("/"),
            intent_api_key=key,
            intent_model=self._selected_model.strip(),
            intent_confidence=float(self.confidence_spin.value()),
        )

    def _save_enabled_only(self) -> None:
        connection = self._build_connection(enabled=self._enabled)
        upsert_env_values(connection_to_env_updates(connection))
        apply_llm_connection(connection)
        self.connection_saved.emit()
        if not self._enabled:
            QMessageBox.information(self, "Intent disabled", "Intent classification is off.")
        else:
            self.status_label.setText(
                "Intent enabled. Fill in the details below, then click Save Intent details."
            )

    def _save_details(self) -> None:
        if not self._enabled:
            QMessageBox.information(self, "Intent disabled", "Enable Intent before saving details.")
            return
        connection = self._build_connection(enabled=True)
        if not connection.intent_model:
            QMessageBox.warning(self, "Missing model", "Select or type an intent model.")
            return
        if connection.intent_backend == "openai" and not connection.intent_base_url:
            QMessageBox.warning(self, "Missing Base URL", "Enter a Base URL for intent.")
            return
        if connection.intent_backend == "gemini" and not connection.intent_api_key:
            QMessageBox.warning(self, "Missing API key", "Paste a Gemini API key.")
            return
        if connection.intent_backend == "openai" and not connection.intent_api_key:
            preset = preset_by_id(connection.intent_provider_id)
            allow_empty = bool(preset and preset.allow_empty_key) or (
                "localhost" in connection.intent_base_url
            )
            if not allow_empty:
                QMessageBox.warning(self, "Missing API key", "Paste an API key for intent.")
                return
        upsert_env_values(connection_to_env_updates(connection))
        apply_llm_connection(connection)
        self._update_status()
        self.connection_saved.emit()
        QMessageBox.information(self, "Saved", "Intent settings saved to .env and applied.")

    def _fetch_models(self) -> None:
        if str(self.backend_combo.currentData() or "") != "openai":
            return
        if self._worker is not None:
            return
        base_url = self.base_url_input.text().strip()
        api_key = self.api_key_input.text().strip()
        if not base_url:
            QMessageBox.warning(self, "Missing Base URL", "Enter an intent Base URL first.")
            return
        self.status_label.setText("Fetching intent models...")
        self.fetch_models_btn.setEnabled(False)

        def work():
            return fetch_remote_models(base_url, api_key)

        self._worker = _Worker(work, self)
        self._worker.finished_ok.connect(self._on_models_fetched)
        self._worker.finished_err.connect(self._on_worker_error)
        self._worker.finished.connect(self._clear_worker)
        self._worker.start()

    def _on_models_fetched(self, models: object) -> None:
        ids = [str(m) for m in (models or [])]
        if not ids:
            self.status_label.setText("No models returned. Type a model ID manually.")
            return
        selected = self._selected_model
        self._all_models = ids
        if selected and selected not in self._all_models:
            self._all_models.insert(0, selected)
        self.model_grid.set_models(self._all_models, selected=selected)
        self.status_label.setText(f"Loaded {len(ids)} intent models.")

    def _on_worker_error(self, message: str) -> None:
        self.status_label.setText(f"Failed: {message}")
        QMessageBox.warning(self, "Request failed", message)

    def _clear_worker(self) -> None:
        self._worker = None
        self.fetch_models_btn.setEnabled(True)
