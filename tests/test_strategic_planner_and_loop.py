"""Strategic planner, agent loop, and web_search registration."""
from __future__ import annotations

import json
from unittest.mock import patch

from brain.agent_loop import AgentLoop, start_task
from brain.planner import Planner
from brain.strategic_planner import (
    format_work_plan_for_user,
    needs_strategic_plan,
    parse_work_plan_payload,
)
from core.session import Session
from core.work_plan import WorkPlan, WorkStep
from tools.executor import ExecutionPlan
from tools.registry import ToolRegistry


def test_needs_strategic_plan_heuristic():
    assert needs_strategic_plan("what time is it") is False
    assert needs_strategic_plan("open notepad") is False
    assert needs_strategic_plan(
        "Research AI in software engineering and create an assignment for me"
    ) is True


def test_parse_work_plan_payload():
    raw = json.dumps(
        {
            "goal": "Write report",
            "steps": [
                {"id": 1, "task": "Search web"},
                {"id": 2, "task": "Draft report"},
            ],
        }
    )
    plan = parse_work_plan_payload(raw, fallback_goal="Write report")
    assert plan is not None
    assert plan.step_count == 2
    assert "Search web" in format_work_plan_for_user(plan)


def test_planner_strategic_path_mocked():
    planner = Planner(registry=ToolRegistry())
    session = Session()
    work = WorkPlan(
        goal="Test goal",
        steps=[WorkStep(id=1, task="Reply with a short greeting")],
    )

    with patch("brain.planner.generate_work_plan", return_value=work):
        with patch(
            "brain.agent_loop.ask_agent_ephemeral",
            return_value='{"tool": "chat", "response": "Hello from step one."}',
        ):
            result = planner.plan_and_execute(
                "Research something and write a report for me",
                session,
            )

    assert result.work_plan is not None
    assert result.task_done is True
    assert "Hello from step one" in result.spoken_text
    assert session.task_state is not None
    assert session.task_state.status.value == "completed"


def test_web_search_tool_missing_key(monkeypatch):
    monkeypatch.delenv("SERPAPI_API_KEY", raising=False)
    monkeypatch.delenv("SERP_API_KEY", raising=False)
    registry = ToolRegistry()
    result = registry.execute("web_search", {"query": "test query"})
    assert result.success is False
    assert "SERPAPI" in result.message.upper()


def test_agent_loop_one_step():
    session = Session()
    start_task(
        session,
        WorkPlan(goal="Greet", steps=[WorkStep(id=1, task="Say hi")]),
    )
    loop = AgentLoop(
        registry=ToolRegistry(),
        guardrails=Planner().guardrails,
        execute_payload=lambda _r, _p, _s: (ExecutionPlan(), "unused"),
    )

    with patch(
        "brain.agent_loop.ask_agent_ephemeral",
        return_value='{"tool": "chat", "response": "Hi there."}',
    ):
        result = loop.run_until_done(session)

    assert result.task_done is True
    assert "Hi there" in result.spoken_text
