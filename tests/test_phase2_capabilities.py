"""Phase 2 capability facades."""
from __future__ import annotations

from core.guardrails import GuardrailManager
from tools.registry import ToolRegistry


def test_capability_tools_registered():
    registry = ToolRegistry()
    for name in ("filesystem", "document", "system", "application", "clipboard"):
        tool = registry.get(name)
        assert tool is not None
        assert getattr(tool, "is_capability", False) is True


def test_document_create_and_read(tmp_path):
    registry = ToolRegistry()
    path = tmp_path / "notes.txt"
    created = registry.execute(
        "document",
        {"operation": "create", "path": str(path), "content": "Hello assignment"},
    )
    assert created.success is True

    read_back = registry.execute("document", {"operation": "read", "path": str(path)})
    assert read_back.success is True
    assert "Hello assignment" in read_back.message


def test_application_open_dispatch():
    registry = ToolRegistry()
    result = registry.execute("application", {"operation": "open", "app": "notepad"})
    assert result.success is True


def test_system_time_dispatch():
    registry = ToolRegistry()
    result = registry.execute("system", {"operation": "time"})
    assert result.success is True
    assert "time" in result.message.lower()


def test_guardrails_capability_shutdown():
    guard = GuardrailManager()
    assert guard.needs_confirmation(
        "system",
        arguments={"operation": "shutdown"},
    ) is True
    assert guard.needs_confirmation(
        "system",
        arguments={"operation": "time"},
    ) is False


def test_guardrails_capability_filesystem_delete():
    guard = GuardrailManager()
    assert guard.needs_confirmation(
        "filesystem",
        arguments={"operation": "delete", "path": "C:\\temp\\x.txt"},
    ) is True


def test_prompt_lists_capabilities_first(tool_registry):
    from tools.base import BaseTool, ToolParameter, ToolResult

    class Echo(BaseTool):
        name = "echo"
        description = "Echo input"
        parameters = (ToolParameter("message", "Text"),)

        def execute(self, params):
            return ToolResult(True, "ok")

    tool_registry.register(Echo())
    section = tool_registry.build_system_prompt_section()
    cap_pos = section.find("- filesystem:")
    other_pos = section.find("Other tools:")
    assert cap_pos >= 0 and other_pos >= 0
    assert cap_pos < other_pos
