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


def _loads_json_lenient(text: str) -> dict[str, Any]:
    """json.loads with repair for invalid backslash escapes from LLMs."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        repaired = _INVALID_ESCAPE_RE.sub(r"\\\\", text)
        data = json.loads(repaired)
    if not isinstance(data, dict):
        raise json.JSONDecodeError("Expected a JSON object", text, 0)
    return data


def parse_agent_payload(raw: str) -> dict[str, Any]:
    """Parse JSON from the LLM, stripping optional markdown fences."""
    cleaned = _FENCE_RE.sub("", (raw or "").strip()).strip()
    try:
        return _loads_json_lenient(cleaned)
    except json.JSONDecodeError:
        # Recover when models wrap JSON with prose or extra tokens.
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
