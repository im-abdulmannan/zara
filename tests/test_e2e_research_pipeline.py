"""End-to-end: strategic plan → research → synthesis → document (mocked LLM)."""
from __future__ import annotations

import json
from unittest.mock import patch

from brain.planner import Planner
from core.session import Session
from core.work_plan import WorkPlan, WorkStep
from tools.registry import ToolRegistry


def test_full_research_to_document_pipeline(tmp_path):
    """Simulates the assignment scenario through Planner + AgentLoop."""
    out_file = tmp_path / "ai_assignment.txt"
    work = WorkPlan(
        goal="Research AI in software engineering and write an assignment",
        steps=[
            WorkStep(id=1, task="Run web_search for AI impact on software engineering"),
            WorkStep(id=2, task="Synthesize and organize findings"),
            WorkStep(id=3, task="Write the assignment document"),
            WorkStep(id=4, task=f"Save assignment to {out_file}"),
        ],
    )

    step_responses = [
        json.dumps(
            {
                "thought": "Searching for recent sources.",
                "tool": "web_search",
                "query": "AI impact software engineering 2026",
            }
        ),
        json.dumps(
            {
                "thought": "Synthesis step — summarizing in chat.",
                "tool": "chat",
                "response": "Findings organized into intro, body, conclusion.",
            }
        ),
        json.dumps(
            {
                "thought": "Writing the assignment file.",
                "tool": "document",
                "operation": "create",
                "path": str(out_file),
                "content": (
                    "Assignment: AI in Software Engineering\n\n"
                    "Introduction\nAI tools change how developers write and review code.\n\n"
                    "Conclusion\nTeams should adopt AI with clear quality gates."
                ),
            }
        ),
        json.dumps(
            {
                "thought": "File already saved.",
                "tool": "chat",
                "response": f"Assignment saved to {out_file}.",
            }
        ),
    ]
    response_iter = iter(step_responses)

    planner = Planner(registry=ToolRegistry())
    session = Session()

    fake_search = (
        True,
        "Web results for 'AI impact software engineering 2026':\n"
        "1. Study on AI coding — https://example.com/study",
        {"query": "AI impact software engineering 2026", "results": []},
    )

    with patch("brain.planner.generate_work_plan", return_value=work):
        with patch("tools.web_search.web_search", return_value=fake_search):
            with patch(
                "brain.agent_loop.ask_agent_ephemeral",
                side_effect=lambda *_a, **_k: next(response_iter),
            ):
                with patch(
                    "brain.research.llm_complete",
                    return_value=(
                        "Key findings:\n- AI assists coding\n"
                        "Outline:\n1. Intro\n2. Impact\n3. Conclusion"
                    ),
                ):
                    with patch(
                        "brain.deliverable.llm_complete",
                        return_value=(
                            "Assignment: AI in Software Engineering\n\n"
                            "Introduction\nAI tools change how developers write code.\n\n"
                            "Conclusion\nTeams should adopt AI with clear quality gates."
                        ),
                    ):
                        with patch(
                            "brain.research.llm_complete_json",
                            return_value='{"action": "continue", "reason": "enough sources"}',
                        ):
                            with patch(
                                "brain.replan.llm_complete_json",
                                return_value='{"action": "continue", "reason": "ok"}',
                            ):
                                result = planner.plan_and_execute(
                                    "Research the impact of AI on software engineering "
                                    "and create an assignment for me.",
                                    session,
                                )

    assert result.work_plan is not None
    assert result.work_plan_outline
    assert result.task_done is True
    assert out_file.is_file()
    text = out_file.read_text(encoding="utf-8")
    assert "Software Engineering" in text
    assert session.task_state is not None
    assert session.task_state.research_notes
    assert session.task_state.research_synthesis
