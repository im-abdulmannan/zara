"""Tests for natural-language and clock time parsing."""
from __future__ import annotations

from datetime import datetime

import pytest

from time_parser.clock import parse_clock_time, parse_next_clock_datetime
from time_parser.exceptions import TimeParseError
from time_parser.when import parse_when


def test_parse_clock_time_24h():
    assert parse_clock_time("14:30") == datetime.strptime("14:30", "%H:%M").time()


def test_parse_clock_time_12h_pm():
    assert parse_clock_time("2:30 pm").hour == 14


def test_parse_clock_time_12h_am_midnight():
    assert parse_clock_time("12 am").hour == 0


def test_parse_clock_time_invalid_raises():
    with pytest.raises(TimeParseError):
        parse_clock_time("not a time")


def test_parse_next_clock_datetime_rolls_to_tomorrow():
    now = datetime(2026, 6, 28, 15, 0, 0)
    result = parse_next_clock_datetime("10:00", now=now)
    assert result.date().day == 29
    assert result.hour == 10


def test_parse_next_clock_datetime_same_day_future():
    now = datetime(2026, 6, 28, 8, 0, 0)
    result = parse_next_clock_datetime("10:00", now=now)
    assert result.date().day == 28
    assert result.hour == 10


def test_parse_when_empty_raises():
    with pytest.raises(TimeParseError):
        parse_when("")
