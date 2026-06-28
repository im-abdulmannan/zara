"""Tests for meeting storage."""
from __future__ import annotations


def test_create_meeting(zara_runtime):
    meeting = zara_runtime.create_meeting(
        title="Team sync",
        date="today",
        time="14:00",
        location="Zoom",
    )
    assert meeting.title == "Team sync"
    assert meeting.location == "Zoom"


def test_meeting_appears_in_calendar_query(zara_runtime):
    """Use a future time so the meeting is not filtered as already past."""
    zara_runtime.create_meeting(title="Standup", date="today", time="23:30")
    result = zara_runtime.query_calendar("what do I have today")
    assert "Standup" in result.answer or "standup" in result.answer.lower()
