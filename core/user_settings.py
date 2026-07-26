"""Local per-user settings (gitignored) — keys and UI choices stay out of ``.env``."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Mapping, MutableMapping, Optional

_ROOT = Path(__file__).resolve().parent.parent
USER_SETTINGS_PATH = _ROOT / "user_settings.json"


def settings_path() -> Path:
    return USER_SETTINGS_PATH


def load_user_settings() -> Dict[str, Any]:
    if not USER_SETTINGS_PATH.exists():
        return {}
    try:
        data = json.loads(USER_SETTINGS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def save_user_settings(updates: Mapping[str, Any]) -> Path:
    """Shallow-merge *updates* into the local settings file and write it."""
    current = load_user_settings()
    _deep_merge(current, dict(updates))
    current["version"] = int(current.get("version") or 1)
    USER_SETTINGS_PATH.write_text(
        json.dumps(current, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return USER_SETTINGS_PATH


def get_app_preference(key: str, default: Any = None) -> Any:
    app = load_user_settings().get("app")
    if not isinstance(app, dict):
        return default
    return app.get(key, default)


def set_app_preferences(**prefs: Any) -> Path:
    return save_user_settings({"app": dict(prefs)})


def _deep_merge(dst: MutableMapping[str, Any], src: Mapping[str, Any]) -> None:
    for key, value in src.items():
        if (
            key in dst
            and isinstance(dst[key], dict)
            and isinstance(value, Mapping)
        ):
            _deep_merge(dst[key], value)  # type: ignore[arg-type]
        else:
            dst[key] = value
