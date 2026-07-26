"""Tests for settings helpers and model/provider UI pieces."""
from __future__ import annotations

import os

import pytest
from PySide6.QtWidgets import QApplication

from core.llm_config import is_free_model, preset_by_id
from ui.env_settings import read_env_values, upsert_env_values
from ui.model_grid import ModelGrid


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


def test_upsert_env_values_roundtrip(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("MODEL_NAME=old-model\nOTHER=keep\n", encoding="utf-8")

    import ui.env_settings as env_settings

    monkeypatch.setattr(env_settings, "ENV_PATH", env_file)
    upsert_env_values({"MODEL_NAME": "new-model", "OPENROUTER_API_KEY": "sk-test"})

    text = env_file.read_text(encoding="utf-8")
    assert "MODEL_NAME=new-model" in text
    assert "OPENROUTER_API_KEY=sk-test" in text
    assert "OTHER=keep" in text
    assert os.environ.get("MODEL_NAME") == "new-model"

    values = read_env_values(["MODEL_NAME", "OPENROUTER_API_KEY", "OTHER"])
    assert values["MODEL_NAME"] == "new-model"
    assert values["OPENROUTER_API_KEY"] == "sk-test"


def test_is_free_model_heuristic():
    assert is_free_model("openai/gpt-oss-20b:free") is True
    assert is_free_model("openrouter/free") is True
    assert is_free_model("gpt-4o") is False


def test_provider_presets_include_chatgpt_and_gemini():
    assert preset_by_id("openai") is not None
    assert preset_by_id("openai").label == "ChatGPT"
    assert preset_by_id("gemini") is not None
    assert preset_by_id("gemini").label == "Gemini"


def test_model_grid_free_filter(qapp):
    grid = ModelGrid(columns=2)
    grid.set_models(
        ["gpt-4o", "openai/gpt-oss-20b:free", "openrouter/free"],
        selected="gpt-4o",
    )
    assert grid.selected_model == "gpt-4o"
    grid.set_free_only(True)
    visible = grid._visible_models()
    assert "gpt-4o" not in visible
    assert "openai/gpt-oss-20b:free" in visible
