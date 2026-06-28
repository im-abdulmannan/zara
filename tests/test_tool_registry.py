"""Tests for tool registry and execution."""
from __future__ import annotations

from tools.base import BaseTool, ToolParameter, ToolResult
from tools.registry import ToolRegistry


class _EchoTool(BaseTool):
    name = "echo"
    description = "Echo input"
    parameters = (ToolParameter("message", "Text to echo"),)

    def execute(self, params):
        return ToolResult(True, params.get("message", ""))


def test_registry_registers_and_finds_tools(tool_registry):
    tool_registry.register(_EchoTool())
    assert tool_registry.get("echo") is not None
    assert "echo" in tool_registry.names()


def test_registry_unknown_tool_returns_failure(tool_registry):
    result = tool_registry.execute("nonexistent", {})
    assert result.success is False
    assert "Unknown action" in result.message


def test_registry_executes_registered_tool(tool_registry):
    tool_registry.register(_EchoTool())
    result = tool_registry.execute("echo", {"message": "hello"})
    assert result.success is True
    assert result.message == "hello"


def test_default_registry_has_all_expected_tools():
    registry = ToolRegistry()
    names = set(registry.names())
    expected = {
        "open_app",
        "close_app",
        "search_installed_apps",
        "open_website",
        "launch_url",
        "search_google",
        "create_folder",
        "open_folder",
        "search_files",
        "rename_file",
        "move_file",
        "copy_file",
        "delete_file",
        "get_time",
        "lock_pc",
        "shutdown_pc",
        "restart_pc",
        "sleep_pc",
        "control_volume",
        "control_brightness",
        "take_screenshot",
        "clipboard_manager",
        "remember",
        "set_reminder",
        "list_reminders",
        "cancel_reminder",
        "create_habit",
        "list_habits",
        "mark_habit_done",
        "pause_habit",
        "resume_habit",
        "delete_habit",
        "query_calendar",
        "create_meeting",
        "create_note",
        "search_notes",
        "list_notes",
        "query_memory",
    }
    assert expected.issubset(names)


def test_build_system_prompt_section_lists_tools(tool_registry):
    tool_registry.register(_EchoTool())
    section = tool_registry.build_system_prompt_section()
    assert "echo" in section
    assert "Tool catalog" in section
