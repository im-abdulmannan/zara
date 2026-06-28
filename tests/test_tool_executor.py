"""Tests for LLM response parsing and multi-step execution."""
from __future__ import annotations

from tools.base import BaseTool, ToolParameter, ToolResult
from tools.executor import (
    ExecutionPlan,
    execute_plan,
    extract_tool_calls,
    parse_agent_payload,
    spoken_response,
)
from tools.registry import ToolRegistry


class _AddTool(BaseTool):
    name = "add"
    description = "Add numbers"
    parameters = (
        ToolParameter("a", "First", type="number"),
        ToolParameter("b", "Second", type="number"),
    )

    def execute(self, params):
        return ToolResult(True, str(int(params["a"]) + int(params["b"])))


class _FailTool(BaseTool):
    name = "fail"
    description = "Always fails"
    parameters = ()

    def execute(self, params):
        return ToolResult(False, "failed")


def test_parse_agent_payload_strips_markdown_fences():
    raw = '```json\n{"tool": "chat", "response": "hi"}\n```'
    payload = parse_agent_payload(raw)
    assert payload["tool"] == "chat"
    assert payload["response"] == "hi"


def test_extract_tool_calls_single_tool():
    calls = extract_tool_calls({"tool": "get_time"})
    assert len(calls) == 1
    assert calls[0]["tool"] == "get_time"


def test_extract_tool_calls_multi_tool():
    calls = extract_tool_calls(
        {"tools": [{"tool": "a"}, {"tool": "b"}], "response": "done"}
    )
    assert len(calls) == 2


def test_extract_tool_calls_ignores_chat():
    assert extract_tool_calls({"tool": "chat", "response": "hi"}) == []


def test_execute_plan_runs_tools_in_order():
    registry = ToolRegistry(tools=[_AddTool()])
    plan = execute_plan({"tools": [{"tool": "add", "a": 1, "b": 2}]}, registry=registry)
    assert plan.all_succeeded is True
    assert plan.steps[0].message == "3"


def test_execute_plan_stops_on_failure():
    registry = ToolRegistry(tools=[_AddTool(), _FailTool()])
    plan = execute_plan(
        {"tools": [{"tool": "add", "a": 1, "b": 1}, {"tool": "fail"}]},
        registry=registry,
    )
    assert len(plan.steps) == 2
    assert plan.all_succeeded is False


def test_spoken_response_prefers_final_response():
    plan = ExecutionPlan(steps=[], final_response="Custom reply")
    assert spoken_response(plan, {}) == "Custom reply"


def test_spoken_response_uses_step_message_for_single_tool():
    plan = ExecutionPlan(
        steps=[type("S", (), {"tool": "x", "success": True, "message": "Done."})()],
    )
    assert spoken_response(plan, {}) == "Done."
