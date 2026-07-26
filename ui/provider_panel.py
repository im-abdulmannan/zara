"""Provider tab: left LLM list + credentials + model card grid."""
from __future__ import annotations

from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from agent import apply_llm_connection, get_active_connection_summary
from core.llm_config import (
    LlmConnection,
    PROVIDER_PRESETS,
    connection_from_env,
    connection_to_env_updates,
    fetch_remote_models,
    load_saved_providers,
    preset_by_id,
    save_custom_provider,
    test_llm_connection,
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


class ProviderPanel(QWidget):
    """Choose LLM from a dropdown; configure key/URL and pick a model card."""

    connection_saved = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._worker: _Worker | None = None
        self._building = False
        self._selected_model = ""
        self._all_models: list[str] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(12)

        self.provider_heading = QLabel("Provider")
        self.provider_heading.setObjectName("sectionTitle")
        root.addWidget(self.provider_heading)

        self.provider_combo = QComboBox()
        self.provider_combo.currentIndexChanged.connect(self._on_provider_combo_changed)
        root.addWidget(QLabel("LLM"))
        root.addWidget(self.provider_combo)

        creds = QFrame()
        creds.setObjectName("settingsCard")
        creds.setStyleSheet(
            """
            QFrame#settingsCard {
                background: rgba(255, 255, 255, 0.03);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 12px;
            }
            """
        )
        creds_layout = QVBoxLayout(creds)
        creds_layout.setContentsMargins(14, 14, 14, 14)
        creds_layout.setSpacing(10)

        key_row = QHBoxLayout()
        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_input.setPlaceholderText("Paste API key — models load automatically")
        key_row.addWidget(self.api_key_input, stretch=1)
        self.show_key_btn = QPushButton("Show")
        self.show_key_btn.setObjectName("ghostBtn")
        self.show_key_btn.setCheckable(True)
        self.show_key_btn.toggled.connect(self._toggle_key_visibility)
        key_row.addWidget(self.show_key_btn)
        creds_layout.addWidget(QLabel("API key (required for most providers)"))
        creds_layout.addLayout(key_row)

        self.base_url_input = QLineEdit()
        self.base_url_input.setPlaceholderText("https://api.example.com/v1")
        creds_layout.addWidget(QLabel("Base URL"))
        creds_layout.addWidget(self.base_url_input)
        root.addWidget(creds)

        # Keep a no-op alias so older helper methods can still disable the control.
        self.provider_list = self.provider_combo

        self._key_fetch_timer = QTimer(self)
        self._key_fetch_timer.setSingleShot(True)
        self._key_fetch_timer.setInterval(450)
        self._key_fetch_timer.timeout.connect(self._fetch_models)
        self.api_key_input.textChanged.connect(self._on_api_key_changed)

        toolbar = QHBoxLayout()
        self.free_only_check = QCheckBox("Show free models only")
        self.free_only_check.toggled.connect(self._on_free_filter_toggled)
        toolbar.addWidget(self.free_only_check)
        toolbar.addStretch()
        self.refresh_models_btn = QPushButton("Refresh models")
        self.refresh_models_btn.setObjectName("ghostBtn")
        self.refresh_models_btn.clicked.connect(self._fetch_models)
        toolbar.addWidget(self.refresh_models_btn)
        root.addLayout(toolbar)

        self.selected_label = QLabel("Selected model: —")
        self.selected_label.setObjectName("hint")
        root.addWidget(self.selected_label)

        self.manual_model_input = QLineEdit()
        self.manual_model_input.setPlaceholderText("Or type a model ID manually")
        self.manual_model_input.textEdited.connect(self._on_manual_model)
        root.addWidget(self.manual_model_input)

        self.model_grid = ModelGrid(columns=2)
        self.model_grid.model_selected.connect(self._on_model_selected)
        root.addWidget(self.model_grid, stretch=1)

        self.status_label = QLabel("Choose an LLM, paste its API key, then save a model.")
        self.status_label.setObjectName("hint")
        self.status_label.setWordWrap(True)
        root.addWidget(self.status_label)

        actions = QHBoxLayout()
        self.test_btn = QPushButton("Test connection")
        self.test_btn.setObjectName("ghostBtn")
        self.test_btn.clicked.connect(self._test_connection)
        actions.addWidget(self.test_btn)
        self.save_custom_btn = QPushButton("Save as custom")
        self.save_custom_btn.setObjectName("ghostBtn")
        self.save_custom_btn.clicked.connect(self._save_as_custom)
        actions.addWidget(self.save_custom_btn)
        actions.addStretch()
        self.apply_btn = QPushButton("Save provider")
        self.apply_btn.setObjectName("primaryBtn")
        self.apply_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.apply_btn.clicked.connect(self._save_and_apply)
        actions.addWidget(self.apply_btn)
        root.addLayout(actions)

        self._populate_provider_list()
        self.reload_from_disk()

    def _populate_provider_list(self) -> None:
        self.provider_combo.blockSignals(True)
        self.provider_combo.clear()
        for preset in PROVIDER_PRESETS:
            self.provider_combo.addItem(preset.label, preset.id)
        for saved in load_saved_providers():
            label = str(saved.get("label") or "Custom")
            self.provider_combo.addItem(f"★ {label}", f"saved:{saved.get('id')}")
            idx = self.provider_combo.count() - 1
            self.provider_combo.setItemData(idx, saved, Qt.ItemDataRole.UserRole + 1)
        self.provider_combo.blockSignals(False)

    def reload_from_disk(self) -> None:
        self._building = True
        self._populate_provider_list()
        connection = connection_from_env()
        self._select_provider_id(connection.provider_id)
        self.base_url_input.setText(connection.base_url)
        self.api_key_input.setText(connection.api_key)
        self._selected_model = connection.model
        self.manual_model_input.setText(connection.model)
        self._all_models = []
        self.model_grid.set_models([], selected=connection.model)
        self.selected_label.setText(f"Selected model: {connection.model or '—'}")
        self.status_label.setText(f"Active: {get_active_connection_summary()}")
        self._building = False
        preset = preset_by_id(connection.provider_id)
        if connection.api_key.strip() or (preset and preset.allow_empty_key):
            self._fetch_models()
        else:
            self.status_label.setText(
                f"Paste your {preset.label if preset else 'provider'} API key to load models."
            )

    def _select_provider_id(self, provider_id: str) -> None:
        idx = self.provider_combo.findData(provider_id)
        if idx < 0:
            idx = self.provider_combo.findData("custom")
        self.provider_combo.setCurrentIndex(max(idx, 0))

    def _current_provider_id(self) -> str:
        data = self.provider_combo.currentData()
        if isinstance(data, str) and data.startswith("saved:"):
            return "custom"
        return str(data or "custom")

    def _on_provider_combo_changed(self, _index: int = 0) -> None:
        if self._building:
            return
        data = self.provider_combo.currentData()
        saved = self.provider_combo.currentData(Qt.ItemDataRole.UserRole + 1)
        if isinstance(data, str) and data.startswith("saved:") and isinstance(saved, dict):
            self.provider_heading.setText(str(saved.get("label") or "Custom"))
            self.base_url_input.setText(str(saved.get("base_url") or ""))
            self.api_key_input.blockSignals(True)
            if saved.get("api_key"):
                self.api_key_input.setText(str(saved.get("api_key")))
            self.api_key_input.blockSignals(False)
            model = str(saved.get("model") or "")
            self._selected_model = model
            self.manual_model_input.setText(model)
            self.selected_label.setText(f"Selected model: {model or '—'}")
            self.status_label.setText(f"Loaded saved provider: {saved.get('label')}")
            self._fetch_models()
            return

        provider_id = str(data or "custom")
        preset = preset_by_id(provider_id)
        if preset is None:
            return
        self.provider_heading.setText(preset.label)
        if preset.base_url:
            self.base_url_input.setText(preset.base_url)
        self.api_key_input.blockSignals(True)
        self.api_key_input.setText(preset.default_api_key or "")
        self.api_key_input.blockSignals(False)
        self.api_key_input.setPlaceholderText(preset.api_key_placeholder)
        self._all_models = []
        self._selected_model = ""
        self.manual_model_input.setText("")
        self.model_grid.set_free_only(self.free_only_check.isChecked())
        self.model_grid.set_models([], selected="")
        if self.api_key_input.text().strip() or preset.allow_empty_key:
            self.status_label.setText(f"Selected {preset.label}. Loading models…")
            self._fetch_models()
        else:
            self.status_label.setText(
                f"Selected {preset.label}. Paste the API key to load models."
            )

    def _on_api_key_changed(self, _text: str) -> None:
        if self._building:
            return
        self._key_fetch_timer.start()

    def _on_free_filter_toggled(self, checked: bool) -> None:
        self.model_grid.set_free_only(checked)
        self.model_grid.set_models(self._all_models, selected=self._selected_model)

    def _on_model_selected(self, model_id: str) -> None:
        self._selected_model = model_id
        self.manual_model_input.setText(model_id)
        self.selected_label.setText(f"Selected model: {model_id}")

    def _on_manual_model(self, text: str) -> None:
        self._selected_model = text.strip()
        self.model_grid.select_model(self._selected_model)
        self.selected_label.setText(f"Selected model: {self._selected_model or '—'}")

    def _toggle_key_visibility(self, checked: bool) -> None:
        mode = QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
        self.api_key_input.setEchoMode(mode)
        self.show_key_btn.setText("Hide" if checked else "Show")

    def current_connection(self) -> LlmConnection:
        """Provider fields merged with current intent settings from env."""
        existing = connection_from_env()
        provider_id = self._current_provider_id()
        preset = preset_by_id(provider_id)
        label = preset.label if preset else "Custom"
        return LlmConnection(
            provider_id=provider_id,
            label=label,
            base_url=self.base_url_input.text().strip().rstrip("/"),
            api_key=self.api_key_input.text().strip(),
            model=self._selected_model.strip(),
            gemini_api_key=existing.gemini_api_key,
            intent_enabled=existing.intent_enabled,
            intent_backend=existing.intent_backend,
            intent_provider_id=existing.intent_provider_id,
            intent_base_url=existing.intent_base_url,
            intent_api_key=existing.intent_api_key,
            intent_model=existing.intent_model,
            intent_confidence=existing.intent_confidence,
        )

    def _validate(self, *, require_key: bool = True) -> LlmConnection | None:
        connection = self.current_connection()
        if not connection.base_url:
            QMessageBox.warning(self, "Missing Base URL", "Enter an OpenAI-compatible Base URL.")
            return None
        if not connection.model:
            QMessageBox.warning(self, "Missing model", "Select a model card or type a model ID.")
            return None
        preset = preset_by_id(connection.provider_id)
        allow_empty = bool(preset and preset.allow_empty_key)
        if require_key and not connection.api_key and not allow_empty:
            QMessageBox.warning(self, "Missing API key", "Paste an API key for this provider.")
            return None
        return connection

    def _set_busy(self, busy: bool) -> None:
        for widget in (
            self.test_btn,
            self.refresh_models_btn,
            self.apply_btn,
            self.save_custom_btn,
            self.provider_combo,
        ):
            widget.setEnabled(not busy)

    def _fetch_models(self) -> None:
        if self._worker is not None:
            return
        base_url = self.base_url_input.text().strip()
        api_key = self.api_key_input.text().strip()
        preset = preset_by_id(self._current_provider_id())
        if not base_url:
            self.status_label.setText("Enter a Base URL first.")
            return
        if not api_key and not (preset and preset.allow_empty_key):
            self._all_models = []
            self.model_grid.set_models([], selected=self._selected_model)
            self.status_label.setText(
                f"Paste your {preset.label if preset else 'provider'} API key to load models."
            )
            return
        self.status_label.setText("Fetching models...")
        self._set_busy(True)

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
        self.status_label.setText(f"Loaded {len(ids)} models.")

    def _test_connection(self) -> None:
        connection = self._validate()
        if connection is None or self._worker is not None:
            return
        self.status_label.setText("Testing connection...")
        self._set_busy(True)

        def work():
            return test_llm_connection(
                connection.base_url,
                connection.api_key,
                connection.model,
            )

        self._worker = _Worker(work, self)
        self._worker.finished_ok.connect(self._on_test_ok)
        self._worker.finished_err.connect(self._on_worker_error)
        self._worker.finished.connect(self._clear_worker)
        self._worker.start()

    def _on_test_ok(self, reply: object) -> None:
        self.status_label.setText(f"Connection OK. Provider replied: {reply!s}")
        QMessageBox.information(self, "Connection OK", "LLM endpoint responded successfully.")

    def _on_worker_error(self, message: str) -> None:
        self.status_label.setText(f"Failed: {message}")
        QMessageBox.warning(self, "Request failed", message)

    def _clear_worker(self) -> None:
        self._worker = None
        self._set_busy(False)

    def _save_and_apply(self) -> None:
        connection = self._validate()
        if connection is None:
            return
        upsert_env_values(connection_to_env_updates(connection))
        apply_llm_connection(connection)
        self.status_label.setText(f"Applied: {get_active_connection_summary()}")
        self.connection_saved.emit()
        QMessageBox.information(self, "Saved", "Provider settings saved to .env and applied.")

    def _save_as_custom(self) -> None:
        connection = self._validate(require_key=False)
        if connection is None:
            return
        from PySide6.QtWidgets import QInputDialog

        label, ok = QInputDialog.getText(
            self, "Custom provider name", "Name:", text="My LLM"
        )
        if not ok or not label.strip():
            return
        save_custom_provider(
            {
                "label": label.strip(),
                "base_url": connection.base_url,
                "model": connection.model,
                "api_key": connection.api_key,
            }
        )
        self.reload_from_disk()
        self.status_label.setText(f"Saved custom provider '{label.strip()}'.")
