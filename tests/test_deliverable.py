"""Deliverable path extraction and auto-save from synthesis."""
from __future__ import annotations

import json
from unittest.mock import patch

from brain.agent_loop import AgentLoop
from brain.deliverable import extract_output_path, write_deliverable
from core.guardrails import GuardrailManager
from core.session import Session
from core.task_state import TaskState
from core.work_plan import WorkPlan, WorkStep
from tools.registry import ToolRegistry


def test_extract_output_path_windows_docx():
    goal = "save it as D:\\zara\\tests\\_out\\ai_assignment.docx"
    assert extract_output_path(goal) == r"D:\zara\tests\_out\ai_assignment.docx"


def test_write_deliverable_txt(tmp_path):
    out = tmp_path / "report.txt"
    state = TaskState(goal=f"Write report to {out}")
    state.research_synthesis = "Introduction\n\nBody\n\nConclusion"
    registry = ToolRegistry()
    ok, msg, path = write_deliverable(state, registry)
    assert ok
    import os

    assert os.path.normpath(path) == os.path.normpath(str(out))
    assert out.read_text(encoding="utf-8") == state.research_synthesis


def test_truncated_json_triggers_auto_save(tmp_path):
    out = tmp_path / "ai_assignment.docx"
    plan = WorkPlan(
        goal=f"Research topic and save {out}",
        steps=[
            WorkStep(id=1, task="Run web_search for topic"),
            WorkStep(id=2, task="Write deliverable: short assignment"),
            WorkStep(id=3, task=f"Save assignment as {out}"),
        ],
    )
    state = TaskState(goal=plan.goal)
    state.start_plan(plan)
    state.advance_step()  # on step 2
    state.research_synthesis = "Intro\n\nSection A\n\nSection B\n\nConclusion"
    state.research_notes = "snippet data"

    session = Session()
    session.task_state = state

    huge_truncated = '{"thought":"x","tools":[{"tool":"document","operation":"create","content":"' + (
        "A" * 5000
    )

    def fake_execute_payload(raw, payload, sess):
        from tools.executor import ExecutionPlan

        return ExecutionPlan(steps=[]), "should not run"

    loop = AgentLoop(
        registry=ToolRegistry(),
        guardrails=GuardrailManager(),
        execute_payload=fake_execute_payload,
    )

    with patch("brain.agent_loop.ask_agent_ephemeral", return_value=huge_truncated):
        with patch("brain.deliverable.llm_complete", return_value=state.research_synthesis):
            result = loop._execute_current_step(session)

    assert result.used_tools
    assert "truncated" in result.spoken_text.lower() or "saved" in result.spoken_text.lower()
    txt_fallback = tmp_path / "ai_assignment.txt"
    assert out.exists() or txt_fallback.exists()
