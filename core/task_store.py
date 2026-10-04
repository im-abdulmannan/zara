"""Persist multi-step task state to disk (separate from chat history)."""
from __future__ import annotations

import json
import os
from typing import Any

from core.logging_config import get_logger
from core.task_state import TaskState

_logger = get_logger(__name__)

_TASK_FILE = os.path.join(os.path.dirname(__file__), "..", "memory", "task_state.json")


def _task_path() -> str:
    return os.path.normpath(_TASK_FILE)


def _read_all() -> dict[str, Any]:
    path = _task_path()
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except Exception as exc:
        _logger.warning("Could not read task store: %s", exc)
        return {}


def _write_all(data: dict[str, Any]) -> None:
    path = _task_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)


def save_task_state(conversation_id: str, state: TaskState | None) -> None:
    """Save or clear task state for a conversation."""
    if not conversation_id:
        return
    store = _read_all()
    if state is None:
        store.pop(conversation_id, None)
    else:
        store[conversation_id] = state.to_dict()
    _write_all(store)


def load_task_state(conversation_id: str) -> TaskState | None:
    """Load task state for a conversation, if any."""
    if not conversation_id:
        return None
    raw = _read_all().get(conversation_id)
    if not isinstance(raw, dict):
        return None
    try:
        return TaskState.from_dict(raw)
    except Exception as exc:
        _logger.warning("Invalid task state for %s: %s", conversation_id, exc)
        return None
