"""Read/write selected settings in the project ``.env`` file."""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Dict, Iterable, Mapping

_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = _ROOT / ".env"

_KEY_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$")


def env_path() -> Path:
    return ENV_PATH


def read_env_values(keys: Iterable[str]) -> Dict[str, str]:
    """Return values for *keys* from process env, falling back to ``.env``."""
    wanted = {key: "" for key in keys}
    for key in wanted:
        current = os.getenv(key)
        if current is not None:
            wanted[key] = current

    if not ENV_PATH.exists():
        return wanted

    file_values = _parse_env_file(ENV_PATH.read_text(encoding="utf-8"))
    for key in wanted:
        if not wanted[key] and key in file_values:
            wanted[key] = file_values[key]
    return wanted


def upsert_env_values(updates: Mapping[str, str]) -> Path:
    """Create or update keys in ``.env`` and mirror them into ``os.environ``."""
    lines: list[str] = []
    if ENV_PATH.exists():
        lines = ENV_PATH.read_text(encoding="utf-8").splitlines()

    remaining = {str(k): "" if v is None else str(v) for k, v in updates.items()}
    rewritten: list[str] = []
    seen: set[str] = set()

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            rewritten.append(line)
            continue
        match = _KEY_RE.match(stripped)
        if not match:
            rewritten.append(line)
            continue
        key = match.group(1)
        if key in remaining:
            rewritten.append(f"{key}={remaining[key]}")
            seen.add(key)
            os.environ[key] = remaining[key]
        else:
            rewritten.append(line)

    for key, value in remaining.items():
        if key not in seen:
            rewritten.append(f"{key}={value}")
            os.environ[key] = value

    ENV_PATH.write_text("\n".join(rewritten) + "\n", encoding="utf-8")
    return ENV_PATH


def _parse_env_file(text: str) -> Dict[str, str]:
    values: Dict[str, str] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = _KEY_RE.match(stripped)
        if match:
            values[match.group(1)] = match.group(2)
    return values
