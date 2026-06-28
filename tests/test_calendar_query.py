"""Tests for calendar natural-language queries."""
from __future__ import annotations

from calendar_query.parser import parse_calendar_question
from calendar_query.models import QueryType


def test_parse_today_question():
    query = parse_calendar_question("what do I have today")
    assert query.query_type is QueryType.TODAY


def test_parse_tomorrow_question():
    query = parse_calendar_question("what's on tomorrow")
    assert query.query_type is QueryType.TOMORROW


def test_parse_all_reminders():
    query = parse_calendar_question("list all reminders")
    assert query.query_type is QueryType.ALL_REMINDERS


def test_parse_next_meeting():
    query = parse_calendar_question("when is my next meeting")
    assert query.query_type is QueryType.NEXT_MEETING


def test_calendar_query_empty_today(zara_runtime):
    result = zara_runtime.query_calendar("what do I have today")
    assert result.answer  # non-empty spoken answer
