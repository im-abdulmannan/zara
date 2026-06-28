"""Tests for domain tools via the tool registry."""
from __future__ import annotations

from datetime import datetime, timedelta

from tools.registry import ToolRegistry


def test_remember_tool(zara_runtime):
    registry = ToolRegistry()
    result = registry.execute("remember", {"kind": "fact", "value": "likes coffee"})
    assert result.success is True


def test_set_reminder_tool(zara_runtime):
    registry = ToolRegistry()
    when = (datetime.now() + timedelta(hours=1)).isoformat()
    result = registry.execute(
        "set_reminder",
        {"title": "stand up", "datetime": when},
    )
    assert result.success is True


def test_list_reminders_empty(zara_runtime):
    registry = ToolRegistry()
    result = registry.execute("list_reminders", {})
    assert result.success is True
    assert "no active reminders" in result.message.lower()


def test_create_note_tool(zara_runtime):
    registry = ToolRegistry()
    result = registry.execute(
        "create_note",
        {"title": "Test", "content": "Body text"},
    )
    assert result.success is True


def test_create_habit_tool(zara_runtime):
    registry = ToolRegistry()
    result = registry.execute(
        "create_habit",
        {"title": "walk", "time": "18:00"},
    )
    assert result.success is True


def test_get_time_tool():
    registry = ToolRegistry()
    result = registry.execute("get_time", {})
    assert result.success is True
    assert "time" in result.message.lower()


def test_tool_validation_missing_params():
    registry = ToolRegistry()
    assert registry.execute("open_app", {}).success is False
    assert registry.execute("search_google", {}).success is False
    assert registry.execute("create_note", {"title": "x"}).success is False
    assert registry.execute("set_reminder", {"title": "x"}).success is False
