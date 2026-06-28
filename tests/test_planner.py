"""Tests for the brain planner (LLM mocked)."""
from __future__ import annotations

from unittest.mock import patch

from brain.planner import Planner
from core.session import Session
from tools.registry import ToolRegistry


def test_planner_chat_response():
    planner = Planner(registry=ToolRegistry())
    session = Session()

    with patch("brain.planner.ask_agent", return_value='{"tool": "chat", "response": "Hello!"}'):
        result = planner.plan_and_execute("hi", session)

    assert result.spoken_text == "Hello!"
    assert result.used_tools is False


def test_planner_executes_tool():
    planner = Planner(registry=ToolRegistry())
    session = Session()

    with patch(
        "brain.planner.ask_agent",
        return_value='{"tool": "get_time"}',
    ):
        result = planner.plan_and_execute("what time is it", session)

    assert result.used_tools is True
    assert result.plan is not None
    assert result.plan.all_succeeded is True
    assert "time" in result.spoken_text.lower()


def test_planner_handles_llm_failure():
    planner = Planner(registry=ToolRegistry())
    session = Session()

    with patch("brain.planner.ask_agent", side_effect=RuntimeError("api down")):
        result = planner.plan_and_execute("hello", session)

    assert "trouble" in result.spoken_text.lower()


def test_planner_handles_invalid_json():
    planner = Planner(registry=ToolRegistry())
    session = Session()

    with patch("brain.planner.ask_agent", return_value="not json"):
        result = planner.plan_and_execute("hello", session)

    assert "didn't understand" in result.spoken_text.lower()
