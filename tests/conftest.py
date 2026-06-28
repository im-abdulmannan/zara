"""Shared pytest fixtures for isolated Zara tests."""
from __future__ import annotations

import pytest

import runtime as runtime_module
from notifications import ConsoleSpeaker
from runtime import ZaraRuntime


@pytest.fixture
def tmp_db_dir(tmp_path, monkeypatch):
    """Point all SQLite databases at temporary files."""
    monkeypatch.setenv("REMINDER_DB_PATH", str(tmp_path / "reminders.sqlite"))
    monkeypatch.setenv("HABIT_DB_PATH", str(tmp_path / "habits.sqlite"))
    monkeypatch.setenv("MEETING_DB_PATH", str(tmp_path / "meetings.sqlite"))
    monkeypatch.setenv("NOTES_DB_PATH", str(tmp_path / "notes.sqlite"))
    monkeypatch.setenv("MEMORY_SYSTEM_DB_PATH", str(tmp_path / "memories.sqlite"))
    monkeypatch.setenv("AUTOMATION_JOBSTORE_URL", "memory")
    return tmp_path


@pytest.fixture
def short_term_memory_path(tmp_path, monkeypatch):
    """Isolate short-term JSON memory from the developer machine."""
    path = tmp_path / "short_term.json"
    monkeypatch.setattr("memory.store.SHORT_TERM_FILE", str(path))
    return path


@pytest.fixture
def zara_runtime(tmp_db_dir):
    """Fresh runtime singleton with a headless speaker."""
    runtime_module._runtime = None

    rt = ZaraRuntime()
    rt.speaker = ConsoleSpeaker()
    rt.start()
    runtime_module._runtime = rt

    yield rt

    rt.shutdown()
    runtime_module._runtime = None


@pytest.fixture(autouse=True)
def reset_memory_singleton():
    """Clear cached memory service so tests respect monkeypatched DB paths."""
    try:
        from memories.service import _default_service

        _default_service.cache_clear()
    except ImportError:
        pass
    yield
    try:
        from memories.service import _default_service

        _default_service.cache_clear()
    except ImportError:
        pass


@pytest.fixture
def tool_registry():
    """Fresh tool registry without global singleton pollution."""
    from tools.registry import ToolRegistry

    return ToolRegistry()
