from datetime import datetime
import os
from unittest.mock import MagicMock, patch

import pytest

from brain.planner import Planner
from calendar_sync.ical_sync import export_meetings_to_ics, import_meetings_from_ics
from core.guardrails import GuardrailManager
from core.session import Session
from meetings.models import Meeting
from notifications.speaker import TTSSpeaker
from tools.registry import ToolRegistry


def test_guardrails_high_risk_detection():
    guardrails = GuardrailManager()

    assert guardrails.is_high_risk("delete_file") is True
    assert guardrails.is_high_risk("shutdown_pc") is True
    assert guardrails.is_high_risk("restart_pc") is True
    assert guardrails.is_high_risk("shutdown_system") is False
    assert guardrails.is_high_risk("get_time") is False


def test_guardrails_confirmation_flow():
    guardrails = GuardrailManager()
    prompt = guardrails.request_confirmation("delete_file", {"path": "C:/important.txt"})

    assert "delete_file" in prompt
    assert guardrails.has_pending is True

    confirmed, action, reply = guardrails.evaluate_user_response("yes, do it")
    assert confirmed is True
    assert action.tool_name == "delete_file"
    assert action.full_payload["tool"] == "delete_file"
    assert guardrails.has_pending is False


def test_guardrails_cancel_flow():
    guardrails = GuardrailManager()
    guardrails.request_confirmation("shutdown_pc", {})

    confirmed, action, reply = guardrails.evaluate_user_response("no cancel that")
    assert confirmed is False
    assert "canceled" in reply
    assert guardrails.has_pending is False


def test_guardrails_ignores_substring_false_positives():
    """'no' must not match inside 'now'; 'yes' must not match inside 'yesterday'."""
    guardrails = GuardrailManager()
    guardrails.request_confirmation("delete_file", {"path": "x.txt"})
    confirmed, _action, _reply = guardrails.evaluate_user_response("run this now")
    assert confirmed is False
    assert guardrails.has_pending is True

    confirmed, _action, _reply = guardrails.evaluate_user_response("maybe yesterday")
    assert confirmed is False
    assert guardrails.has_pending is True


def test_guardrails_prefers_cancel_when_both_yes_and_no():
    guardrails = GuardrailManager()
    guardrails.request_confirmation("shutdown_pc", {})
    confirmed, action, _reply = guardrails.evaluate_user_response("yes no wait")
    assert confirmed is False
    assert action is None
    assert guardrails.has_pending is False


def test_planner_defers_high_risk_until_confirmed():
    planner = Planner(registry=ToolRegistry())
    session = Session()

    with patch(
        "brain.planner.ask_agent",
        return_value='{"tool": "shutdown_pc", "response": "Shutting down."}',
    ):
        first = planner.plan_and_execute("shutdown the computer", session)

    assert first.awaiting_confirmation is True
    assert first.used_tools is False
    assert planner.guardrails.has_pending is True

    with patch.object(planner.registry, "execute") as execute_mock:
        execute_mock.return_value = MagicMock(success=True, message="Shutting down the computer.")
        second = planner.plan_and_execute("yes", session)

    assert second.used_tools is True
    execute_mock.assert_called()
    assert planner.guardrails.has_pending is False


def test_planner_cancels_high_risk_on_no():
    planner = Planner(registry=ToolRegistry())
    session = Session()

    with patch(
        "brain.planner.ask_agent",
        return_value='{"tool": "restart_pc"}',
    ):
        planner.plan_and_execute("restart please", session)

    result = planner.plan_and_execute("no", session)
    assert result.used_tools is False
    assert "canceled" in result.spoken_text.lower()
    assert planner.guardrails.has_pending is False


def test_ical_export_and_import(tmp_path):
    ics_file = str(tmp_path / "test_schedule.ics")

    now = datetime.now()
    meeting = Meeting(id="1", title="Sync Meeting", date=now.date(), time=now.time())

    path = export_meetings_to_ics([meeting], ics_file)
    assert os.path.exists(path)

    mock_service = MagicMock()
    count = import_meetings_from_ics(path, mock_service)
    assert count == 1
    mock_service.create_meeting.assert_called_once()
    kwargs = mock_service.create_meeting.call_args.kwargs
    assert kwargs["title"] == "Sync Meeting"


def test_tts_speaker_stop():
    speaker = TTSSpeaker(speak_func=MagicMock())
    speaker.stop()
