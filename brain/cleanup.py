"""Remove stray deliverable files after multi-step tasks."""
from __future__ import annotations

import os
import re
from typing import Any

from brain.deliverable import extract_output_path
from core.logging_config import get_logger
from core.task_state import TaskState
from tools.registry import ToolRegistry

_logger = get_logger(__name__)

_DOCUMENT_EXTS = frozenset({".docx", ".txt", ".md", ".pdf", ".rtf"})
_SAVED_PATH_RE = re.compile(
    r"(?:Document saved to|Created|saved to|Saved to|Deleted)\s+"
    r"([A-Za-z]:[\\/][^\s\"']+\.(?:docx|txt|md|pdf|rtf)|"
    r"[^\s\"']+\.(?:docx|txt|md|pdf|rtf))",
    re.I,
)


def norm_path(path: str) -> str:
    if not path or not str(path).strip():
        return ""
    return os.path.normcase(
        os.path.normpath(os.path.abspath(os.path.expanduser(str(path).strip())))
    )


def resolve_intended_deliverable(state: TaskState) -> str:
    explicit = (getattr(state, "intended_deliverable_path", None) or "").strip()
    if explicit:
        return norm_path(explicit)
    from_goal = extract_output_path(state.goal) or ""
    return norm_path(from_goal) if from_goal else ""


def _paths_from_message(message: str) -> list[str]:
    found: list[str] = []
    for match in _SAVED_PATH_RE.finditer(message or ""):
        raw = match.group(1).strip().rstrip(".")
        if raw:
            found.append(raw)
    return found


def record_deliverable_file(state: TaskState, tool_results: list[dict[str, Any]]) -> None:
    """Track document writes and paths mentioned in tool messages."""
    for result in tool_results:
        if not result.get("success"):
            continue
        tool = str(result.get("tool") or "")
        params = result.get("params") if isinstance(result.get("params"), dict) else {}
        message = str(result.get("message") or "")

        paths: list[str] = []
        if tool == "document":
            op = str(params.get("operation") or "").lower()
            if op in {"create", "to_docx"}:
                for key in ("path", "destination"):
                    value = str(params.get(key) or "").strip()
                    if value:
                        paths.append(value)
        for value in _paths_from_message(message):
            paths.append(value)

        for raw in paths:
            absolute = norm_path(raw)
            if not absolute:
                continue
            if absolute not in state.files_touched:
                state.files_touched.append(absolute)
            ext = os.path.splitext(absolute)[1].lower()
            if ext in _DOCUMENT_EXTS and absolute not in state.deliverable_files:
                state.deliverable_files.append(absolute)


def cleanup_stray_deliverables(
    state: TaskState,
    registry: ToolRegistry,
) -> tuple[list[str], list[str]]:
    """
    Delete extra deliverable files created during the task, keeping the user path.

    Returns (deleted_paths, error_messages).
    """
    intended = resolve_intended_deliverable(state)
    if not intended:
        return [], []

    deleted: list[str] = []
    errors: list[str] = []

    candidates = list(dict.fromkeys(state.deliverable_files or state.files_touched))
    for raw in candidates:
        path = norm_path(raw)
        if not path or path == intended:
            continue
        if not os.path.isfile(path):
            continue
        ext = os.path.splitext(path)[1].lower()
        if ext not in _DOCUMENT_EXTS:
            continue
        result = registry.execute("delete_file", {"path": path})
        if result.success:
            deleted.append(path)
            if path in state.deliverable_files:
                state.deliverable_files.remove(path)
            if path in state.files_touched:
                state.files_touched.remove(path)
            _logger.info("Task cleanup removed stray file: %s", path)
        else:
            errors.append(result.message or f"Could not delete {path}")

    return deleted, errors


def cleanup_summary(deleted: list[str], errors: list[str]) -> str:
    if not deleted and not errors:
        return ""
    parts: list[str] = []
    if deleted:
        names = ", ".join(os.path.basename(p) for p in deleted)
        parts.append(f"Removed extra deliverable file(s): {names}.")
    if errors:
        parts.append("Some cleanup deletes failed: " + "; ".join(errors[:3]))
    return " ".join(parts)
