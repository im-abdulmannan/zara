"""Clipboard tools for reading and copying text."""
from __future__ import annotations

from typing import Any, Mapping

from tools.base import BaseTool, ToolParameter, ToolResult
from tools.registration import register_tool


def _read_clipboard_text() -> tuple[bool, str, str]:
    """Return ``(success, message, text)``."""
    try:
        import win32clipboard

        win32clipboard.OpenClipboard()
        try:
            if win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_UNICODETEXT):
                data = win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
            else:
                data = ""
        finally:
            win32clipboard.CloseClipboard()
    except Exception as exc:
        return False, f"Could not read clipboard: {exc}", ""

    if not data:
        return True, "The clipboard is empty.", ""
    preview = data[:200] + ("..." if len(data) > 200 else "")
    return True, f"Clipboard contains: {preview}", data


def _write_clipboard_text(text: str) -> tuple[bool, str]:
    """Return ``(success, message)``."""
    try:
        import win32clipboard

        win32clipboard.OpenClipboard()
        try:
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardText(str(text))
        finally:
            win32clipboard.CloseClipboard()
        return True, "Copied to clipboard."
    except Exception as exc:
        return False, f"Could not write clipboard: {exc}"


@register_tool
class CopyClipboardTool(BaseTool):
    name = "copy_clipboard"
    description = "Copy text to the system clipboard."
    parameters = (
        ToolParameter("text", "Text to copy to the clipboard"),
    )

    def execute(self, params: Mapping[str, Any]) -> ToolResult:
        text = params.get("text")
        if text is None:
            return ToolResult(False, "What should I copy to the clipboard?")
        success, message = _write_clipboard_text(str(text))
        if not success:
            return ToolResult(False, message)
        return ToolResult(True, message, {"text": str(text)})


@register_tool
class ReadClipboardTool(BaseTool):
    name = "read_clipboard"
    description = "Read text from the system clipboard."
    parameters: tuple[ToolParameter, ...] = ()

    def execute(self, params: Mapping[str, Any]) -> ToolResult:
        success, message, text = _read_clipboard_text()
        if not success:
            return ToolResult(False, message)
        return ToolResult(True, message, {"text": text})


@register_tool
class ClipboardManagerTool(BaseTool):
    """Backward-compatible read/write clipboard tool."""

    name = "clipboard_manager"
    description = "Read from or write to the system clipboard."
    parameters = (
        ToolParameter("action", "One of: read, write"),
        ToolParameter("text", "Text to copy when action is write", required=False),
    )

    def execute(self, params: Mapping[str, Any]) -> ToolResult:
        action = (params.get("action") or "").lower().strip()
        if action == "read":
            success, message, text = _read_clipboard_text()
            if not success:
                return ToolResult(False, message)
            return ToolResult(True, message, {"text": text})

        if action == "write":
            text = params.get("text")
            if text is None:
                return ToolResult(False, "What should I copy to the clipboard?")
            success, message = _write_clipboard_text(str(text))
            if not success:
                return ToolResult(False, message)
            return ToolResult(True, message, {"text": str(text)})

        return ToolResult(False, "Clipboard action must be read or write.")
