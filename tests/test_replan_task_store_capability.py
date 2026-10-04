"""Replanning, task persistence, and filesystem capability."""
from __future__ import annotations

import json
from unittest.mock import patch

from brain.replan import (
    ReplanDecision,
    apply_replan,
    parse_replan_payload,
    should_replan_after,
)
from core.session import Session
from core.task_state import StepObservation, TaskState, TaskStatus
from core.task_store import load_task_state, save_task_state
from core.work_plan import WorkPlan, WorkStep
from tools.registry import ToolRegistry


def test_should_replan_after_web_search():
    from core.task_state import TaskState

    obs = StepObservation(
        step_id=2,
        summary="results",
        tool_results=[{"tool": "web_search", "success": True, "message": "ok"}],
    )
    state = TaskState(search_queries_run=["one"])
    assert should_replan_after(obs, state) is True
    state.search_queries_run = ["a", "b", "c"]
    state.research_notes = "x" * 500
    assert should_replan_after(obs, state) is False


def test_parse_and_apply_replan():
    raw = json.dumps(
        {
            "action": "revise",
            "reason": "need more angles",
            "remaining_steps": [
                {"task": "Run web_search for productivity studies"},
                {"task": "Draft outline"},
            ],
        }
    )
    decision = parse_replan_payload(raw)
    assert decision is not None
    assert decision.action == "revise"

    state = TaskState(
        goal="Report",
        plan=WorkPlan(
            goal="Report",
            steps=[
                WorkStep(id=1, task="Research"),
                WorkStep(id=2, task="Write"),
                WorkStep(id=3, task="Save"),
            ],
        ),
        current_step_id=2,
        completed_step_ids=[1],
    )
    changed = apply_replan(state, decision)
    assert changed is True
    assert state.plan.step_count == 3
    assert state.current_step_id == 2
    assert "web_search" in state.plan.steps[1].task.lower()


def test_task_store_round_trip(tmp_path, monkeypatch):
    store_file = tmp_path / "task_state.json"
    monkeypatch.setattr("core.task_store._TASK_FILE", str(store_file))

    session = Session()
    state = TaskState(goal="Resume job")
    state.start_plan(
        WorkPlan(goal="Resume job", steps=[WorkStep(id=1, task="Find file")])
    )
    save_task_state(session.conversation_id, state)

    loaded = load_task_state(session.conversation_id)
    assert loaded is not None
    assert loaded.goal == "Resume job"
    assert loaded.current_step_id == 1

    save_task_state(session.conversation_id, None)
    assert load_task_state(session.conversation_id) is None


def test_filesystem_capability_list(tmp_path):
    registry = ToolRegistry()
    sample = tmp_path / "hello.txt"
    sample.write_text("hi", encoding="utf-8")

    read_result = registry.execute(
        "filesystem",
        {"operation": "read", "path": str(sample)},
    )
    assert read_result.success is True
    assert "hi" in read_result.message

    list_result = registry.execute(
        "filesystem",
        {"operation": "list", "path": str(tmp_path)},
    )
    assert list_result.success is True


def test_maybe_replan_skips_when_not_needed():
    from brain.replan import maybe_replan

    state = TaskState(
        goal="Open app",
        plan=WorkPlan(goal="Open app", steps=[WorkStep(id=1, task="Open notepad")]),
        current_step_id=1,
    )
    obs = StepObservation(step_id=1, summary="Opened notepad.", success=True)
    with patch("brain.replan.llm_complete_json") as mock_llm:
        assert maybe_replan(state, obs) is False
        mock_llm.assert_not_called()
