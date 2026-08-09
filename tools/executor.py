"""Multi-step tool execution and LLM response normalization."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from tools.logging_config import get_logger
from tools.registry import ToolRegistry, get_registry

_logger = get_logger(__name__)

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)
# Invalid escapes like Windows paths (C:\Users) break json.loads.
_INVALID_ESCAPE_RE = re.compile(r'\\(?!["\\/bfnrtu]|u[0-9a-fA-F]{4})')


@dataclass
class ExecutionStep:
    tool: str
    params: dict[str, Any]
    success: bool
    message: str


@dataclass
class ExecutionPlan:
    steps: list[ExecutionStep] = field(default_factory=list)
    final_response: str = ""

    @property
    def all_succeeded(self) -> bool:
        return all(step.success for step in self.steps)


def _extract_balanced_object(text: str) -> str | None:
    """Return the first balanced ``{...}`` object in *text*, if any."""
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    in_string = False
    escape = False
    for index in range(start, len(text)):
        ch = text[index]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return None


def _loads_json_lenient(text: str) -> dict[str, Any]:
    """json.loads with repair for invalid escapes and trailing braces from LLMs."""
    candidates = [text]
    # Common free-model glitch: extra closing brace(s), e.g. ``...false}}``.
    stripped = text.rstrip()
    while stripped.endswith("}}"):
        stripped = stripped[:-1]
        candidates.append(stripped)

    balanced = _extract_balanced_object(text)
    if balanced and balanced not in candidates:
        candidates.append(balanced)

    last_error: Exception | None = None
    for candidate in candidates:
        try:
            data = json.loads(candidate)
        except json.JSONDecodeError as exc:
            last_error = exc
            try:
                repaired = _INVALID_ESCAPE_RE.sub(r"\\\\", candidate)
                data = json.loads(repaired)
            except json.JSONDecodeError as exc2:
                last_error = exc2
                continue
        if isinstance(data, dict):
            return data
        last_error = json.JSONDecodeError("Expected a JSON object", candidate, 0)

    if last_error is not None:
        raise last_error
    raise json.JSONDecodeError("Expected a JSON object", text, 0)


def parse_agent_payload(raw: str) -> dict[str, Any]:
    """Parse JSON from the LLM, stripping optional markdown fences."""
    cleaned = _FENCE_RE.sub("", (raw or "").strip()).strip()
    try:
        return _loads_json_lenient(cleaned)
    except json.JSONDecodeError:
        # Recover when models wrap JSON with prose or extra tokens.
        balanced = _extract_balanced_object(cleaned)
        if balanced:
            return _loads_json_lenient(balanced)
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start >= 0 and end > start:
            return _loads_json_lenient(cleaned[start : end + 1])
        raise

def extract_tool_calls(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Normalise single-tool and multi-tool LLM payloads."""
    if not isinstance(payload, dict):
        return []

    if isinstance(payload.get("tools"), list):
        calls = []
        for item in payload["tools"]:
            if isinstance(item, dict) and item.get("tool"):
                calls.append(dict(item))
        return calls

    if payload.get("tool") and payload.get("tool") != "chat":
        return [dict(payload)]

    return []


def normalize_tool_params(call: dict[str, Any]) -> dict[str, Any]:
    """Flatten LLM tool payloads, including nested ``params`` objects."""
    data = dict(call or {})
    nested = data.pop("params", None)
    data.pop("tool", None)
    data.pop("response", None)
    data.pop("thought", None)
    if isinstance(nested, dict):
        merged = dict(nested)
        merged.update(data)
        return merged
    return data


def execute_plan(
    payload: dict[str, Any],
    registry: ToolRegistry | None = None,
) -> ExecutionPlan:
    """Execute all tool calls in *payload* sequentially."""
    registry = registry or get_registry()
    plan = ExecutionPlan(
        final_response=str(payload.get("response") or "").strip(),
    )

    for call in extract_tool_calls(payload):
        tool_name = str(call.get("tool", "")).strip()
        if not tool_name:
            continue
        params = normalize_tool_params(call)
        result = registry.execute(tool_name, params)
        plan.steps.append(
            ExecutionStep(
                tool=tool_name,
                params=params,
                success=result.success,
                message=result.message,
            )
        )
        if not result.success:
            _logger.warning("Stopping plan after failed tool=%s", tool_name)
            break

    return plan


def spoken_response(plan: ExecutionPlan, payload: dict[str, Any]) -> str:
    """Choose the best spoken reply after executing a plan."""
    if plan.final_response:
        return plan.final_response

    if payload.get("tool") == "chat":
        return str(payload.get("response") or "Okay.")

    if plan.steps:
        if len(plan.steps) == 1:
            return plan.steps[0].message
        if plan.all_succeeded:
            return " ".join(step.message for step in plan.steps)
        for step in reversed(plan.steps):
            if not step.success:
                return step.message

    return str(payload.get("response") or "Done.")
