"""Phase 3: research accumulation and synthesis."""
from __future__ import annotations

from unittest.mock import patch

from brain.research import (
    accumulate_research,
    ensure_synthesis_before_write,
    followup_search_queries,
    has_research_content,
    is_write_step,
    synthesize_research,
)
from core.task_state import StepObservation, TaskState
from core.work_plan import WorkPlan, WorkStep


def test_accumulate_web_search_notes():
    state = TaskState(goal="Report on AI")
    obs = StepObservation(
        step_id=1,
        summary="search done",
        tool_results=[
            {
                "tool": "web_search",
                "success": True,
                "message": "Web results for 'ai':\n1. Study — http://example.com",
                "params": {"query": "ai impact"},
            }
        ],
    )
    accumulate_research(state, obs)
    assert has_research_content(state)
    assert "example.com" in state.research_notes
    assert state.search_queries_run == ["ai impact"]


def test_synthesize_research_mocked():
    state = TaskState(
        goal="Assignment",
        research_notes="Web results:\n1. Paper A — http://a.test",
        search_queries_run=["ai dev"],
    )
    with patch(
        "brain.research.llm_complete",
        return_value="Key findings:\n- Point one\nOutline:\n1. Intro",
    ):
        text = synthesize_research(state)
    assert "Point one" in text
    assert state.research_synthesis == text


def test_ensure_synthesis_before_write_step():
    state = TaskState(
        goal="Write report",
        research_notes="snippet data",
    )
    assert is_write_step("Write the assignment document")
    with patch(
        "brain.research.synthesize_research",
        return_value="Brief ready",
    ) as mock_syn:
        result = ensure_synthesis_before_write(state, "Write the final report")
    assert result == "Brief ready"
    mock_syn.assert_called_once()


def test_followup_queries_mocked():
    state = TaskState(goal="AI essay", search_queries_run=["ai 2026"])
    with patch(
        "brain.research.llm_complete_json",
        return_value='{"queries":["ai developer productivity","ai code quality studies"]}',
    ):
        queries = followup_search_queries(state)
    assert len(queries) == 2


def test_task_state_persists_research_fields():
    state = TaskState(
        goal="G",
        research_notes="notes",
        research_synthesis="brief",
        search_queries_run=["q1"],
    )
    restored = TaskState.from_dict(state.to_dict())
    assert restored.research_synthesis == "brief"
    assert restored.search_queries_run == ["q1"]
