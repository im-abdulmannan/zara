"""In-memory live status shared between the voice loop and the web API."""
from __future__ import annotations

import threading
from typing import Any, Dict

_lock = threading.Lock()
_status: Dict[str, Any] = {
    "state": "idle",
    "subtitle": 'Say "Hey Zara" to start...',
    "active_model": "",
}


def update_status(**fields: Any) -> None:
    with _lock:
        for key, value in fields.items():
            if value is not None:
                _status[key] = value


def get_status() -> Dict[str, Any]:
    with _lock:
        return dict(_status)
