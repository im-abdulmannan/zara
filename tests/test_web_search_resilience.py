"""Web search retry and research-failure recovery."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from brain.agent_loop import AgentLoop, start_task
from brain.planner import Planner
from core.session import Session
from core.task_state import TaskStatus
from core.work_plan import WorkPlan, WorkStep
from tools.executor import ExecutionPlan, ExecutionStep
from tools.registry import ToolRegistry


def test_web_search_retries_on_timeout():
    import tools.web_search as ws

    calls = {"n": 0}

    def fake_urlopen(*_args, **_kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise TimeoutError("The read operation timed out")
        response = MagicMock()
        response.read.return_value = b'{"organic_results":[{"title":"T","link":"http://x","snippet":"S"}]}'
        response.__enter__ = lambda s: s
        response.__exit__ = lambda *a: None
        return response

    with patch.dict("os.environ", {"SERPAPI_API_KEY": "test", "SERPAPI_RETRY_ATTEMPTS": "2"}):
        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            ok, message, _ = ws.web_search("test query", num=1)
    assert ok is True
    assert calls["n"] == 2
    assert "T" in message


def test_agent_continues_after_search_timeout_with_enough_research():
    session = Session()
    start_task(
        session,
        WorkPlan(
            goal="Write report",
            steps=[WorkStep(id=1, task="Extra search"), WorkStep(id=2, task="Write doc")],
        ),
    )
    state = session.task_state
    assert state is not None
    state.search_queries_run = ["q1", "q2"]
    state.research_notes = "x" * 600

    loop = AgentLoop(
        registry=ToolRegistry(),
        guardrails=Planner().guardrails,
        execute_payload=lambda _r, _p, _s: (
            ExecutionPlan(
                steps=[
                    ExecutionStep(
                        tool="web_search",
                        params={"query": "q3"},
                        success=False,
                        message="Web search failed: timed out",
                    )
                ]
            ),
            "Web search failed: timed out",
        ),
    )

    with patch(
        "brain.agent_loop.ask_agent_ephemeral",
        return_value='{"tool":"web_search","query":"q3"}',
    ):
        result = loop._execute_current_step(session)

    assert state.status != TaskStatus.FAILED
    assert "enough" in result.spoken_text.lower() or "Continuing" in result.spoken_text
