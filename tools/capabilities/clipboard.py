"""Clipboard capability — read and write text."""
from __future__ import annotations

from typing import Any, ClassVar, Mapping

from tools.base import BaseTool, ToolParameter, ToolResult
from tools.registry import get_registry
from tools.registration import register_tool


@register_tool
class ClipboardCapabilityTool(BaseTool):
    name = "clipboard"
    description = "Clipboard capability: read or write plain text."
    is_capability: ClassVar[bool] = True
    parameters = (
        ToolParameter("operation", "One of: read, write"),
        ToolParameter("text", "Text to write when operation is write", required=False),
    )
    intent_keywords = ("clipboard", "copy to clipboard", "paste")

    def execute(self, params: Mapping[str, Any]) -> ToolResult:
        operation = str(params.get("operation") or "").strip().lower()
        registry = get_registry()

        if operation == "read":
            return registry.execute("read_clipboard", {})
        if operation == "write":
            return registry.execute(
                "clipboard_manager",
                {"action": "write", "text": params.get("text")},
            )

        return ToolResult(False, "clipboard requires operation: read or write.")
