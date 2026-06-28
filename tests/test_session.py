"""Tests for multi-turn session tracking."""
from __future__ import annotations

from core.session import Session


def test_session_records_user_and_assistant_turns():
    session = Session()
    session.add_user_turn("hello")
    session.add_assistant_turn("hi there")

    assert len(session.history) == 2
    assert session.history[0] == {"role": "user", "content": "hello"}
    assert session.history[1] == {"role": "assistant", "content": "hi there"}


def test_session_records_tool_history():
    session = Session()
    session.record_tool("get_time", True, "The current time is noon.")

    assert len(session.tool_history) == 1
    assert session.tool_history[0]["tool"] == "get_time"
    assert session.tool_history[0]["success"] is True


def test_session_touch_updates_activity():
    session = Session()
    before = session.last_activity
    session.touch()
    assert session.last_activity >= before
