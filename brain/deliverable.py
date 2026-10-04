"""Save final documents from research synthesis (avoids huge tool JSON)."""
from __future__ import annotations

import re
from typing import Any

from agent import llm_complete
from core.logging_config import get_logger
from core.task_state import TaskState
from tools.registry import ToolRegistry

_logger = get_logger(__name__)

_DRIVE_PATH_RE = re.compile(
    r"([A-Za-z]:[\\/](?:[^\"']+[\\/])*[^\"']+\.(?:docx|txt|md))",
    re.I,
)


def _normalize_path(path: str) -> str:
    import os

    return os.path.normpath(path)


def extract_output_path(*texts: str) -> str | None:
    for text in texts:
        if not text:
            continue
        match = _DRIVE_PATH_RE.search(text)
        if match:
            return _normalize_path(match.group(1))
    return None


def is_save_step(task: str) -> bool:
    lowered = (task or "").lower()
    return any(
        word in lowered
        for word in ("save", "write", "deliverable", "document", "assignment", "report")
    )


_ASSIGNMENT_SYSTEM = """You write polished assignment documents from a research brief for Microsoft Word (.docx).

Structure:
- Title on the first line (plain text, no # or **).
- Section headings on their own line: Introduction, then two body section titles, then Conclusion.
- Normal paragraphs separated by blank lines.

Formatting rules:
- Do NOT use markdown (# headings, **bold**, bullet syntax, or code fences).
- Write plain sentences; emphasis belongs in wording, not markup.
- Keep citations as inline URLs from the brief where helpful."""


def _compose_assignment_body(state: TaskState) -> str:
    brief = (state.research_synthesis or state.research_notes or "").strip()
    if not brief:
        return ""
    if len(brief) < 2500 and "Introduction" in brief:
        return brief
    raw = llm_complete(
        [
            {"role": "system", "content": _ASSIGNMENT_SYSTEM},
            {
                "role": "user",
                "content": (
                    f"Goal: {state.goal}\n\nResearch brief:\n{brief[:14000]}\n\n"
                    "Write the full assignment now."
                ),
            },
        ]
    )
    return (raw or brief).strip()


def write_deliverable(
    state: TaskState,
    registry: ToolRegistry,
    *,
    step_hint: str = "",
) -> tuple[bool, str, str]:
    """Write assignment/report to disk using the document capability."""
    path = extract_output_path(state.goal, step_hint)
    if not path:
        return False, "I could not find an output file path in the request.", ""

    body = _compose_assignment_body(state)
    if not body:
        return False, "There is no research content to save yet.", ""

    if path.lower().endswith(".docx"):
        result = registry.execute(
            "document",
            {"operation": "to_docx", "path": path, "content": body},
        )
        if not result.success and "python-docx" in (result.message or "").lower():
            fallback = path[:-5] + ".txt" if path.lower().endswith(".docx") else path + ".txt"
            result = registry.execute(
                "document",
                {"operation": "create", "path": fallback, "content": body},
            )
            if result.success:
                state.files_touched.append(fallback)
                if fallback not in state.deliverable_files:
                    state.deliverable_files.append(fallback)
                msg = f"{result.message} (Install python-docx for DOCX; wrote text file instead.)"
                _logger.info("Deliverable saved to %s (docx fallback)", fallback)
                return True, msg, fallback
    else:
        result = registry.execute(
            "document",
            {"operation": "create", "path": path, "content": body},
        )

    if result.success:
        from brain.cleanup import norm_path

        absolute = norm_path(path)
        state.files_touched.append(absolute)
        if absolute not in state.deliverable_files:
            state.deliverable_files.append(absolute)
        _logger.info("Deliverable saved to %s", absolute)
    return result.success, result.message, path


def try_extract_tool_payload(raw: str) -> dict[str, Any] | None:
    """Best-effort parse when the model returns truncated JSON."""
    text = (raw or "").strip()
    if not text.startswith("{"):
        start = text.find("{")
        if start < 0:
            return None
        text = text[start:]
    try:
        from tools.executor import parse_agent_payload

        return parse_agent_payload(text)
    except Exception:
        pass
    if '"tools"' in text and text.count("{") > text.count("}"):
        repaired = text + "}" * (text.count("{") - text.count("}"))
        try:
            from tools.executor import parse_agent_payload

            return parse_agent_payload(repaired)
        except Exception:
            return None
    return None
