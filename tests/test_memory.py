"""Tests for short-term memory capture and task tracking."""
from __future__ import annotations

from memory.store import (
    add_task,
    auto_capture,
    clear_short_term,
    get_tasks,
)


def test_remember_name(zara_runtime):
    zara_runtime.remember("name", "Alice")
    memories = zara_runtime.query_memory("name")
    assert any(m.value == "Alice" for m in memories)


def test_add_and_get_tasks(short_term_memory_path):
    clear_short_term()
    add_task("buy milk")
    assert "buy milk" in get_tasks()


def test_auto_capture_name(zara_runtime):
    captured = auto_capture("My name is Bob")
    assert any("Bob" in item for item in captured)
    memories = zara_runtime.query_memory("name")
    assert any(m.value == "Bob" for m in memories)


def test_auto_capture_task_without_time(short_term_memory_path):
    clear_short_term()
    captured = auto_capture("I need to finish the report")
    assert captured
    assert "finish the report" in get_tasks()[0]


def test_auto_capture_skips_timed_reminder_as_task(short_term_memory_path):
    clear_short_term()
    auto_capture("Remind me at 5pm to call mom")
    assert get_tasks() == []


def test_memory_summary_includes_name(zara_runtime):
    zara_runtime.remember("name", "Carol")
    summary = zara_runtime.memory_summary_text()
    assert "Carol" in summary
