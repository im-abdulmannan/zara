"""Filesystem capability — one tool, many operations."""
from __future__ import annotations

import os
from typing import Any, ClassVar, Mapping

from tools.base import BaseTool, ToolParameter, ToolResult
from tools.registry import get_registry
from tools.registration import register_tool

_MAX_READ_BYTES = 96_000


@register_tool
class FilesystemCapabilityTool(BaseTool):
    """High-level filesystem access (dispatches to granular tools)."""

    name = "filesystem"
    description = (
        "Filesystem capability: search, list, open, read text, create folder, "
        "copy, move, rename, delete, or count items."
    )
    is_capability: ClassVar[bool] = True
    parameters = (
        ToolParameter(
            "operation",
            "One of: search, list, open, read, create, copy, move, rename, delete, count",
        ),
        ToolParameter("path", "File or folder path", required=False),
        ToolParameter("query", "Search name or pattern", required=False),
        ToolParameter("directory", "Search/list root directory", required=False),
        ToolParameter("destination", "Target path for copy/move", required=False),
        ToolParameter("new_name", "New name for rename", required=False),
        ToolParameter("kind", "file, folder, or both (search)", required=False),
        ToolParameter("open", "Open in Explorer after search (true/false)", required=False),
        ToolParameter("recursive", "Recursive count (true/false)", required=False),
    )
    intent_keywords = ("filesystem", "file on disk", "save to", "my documents")

    def execute(self, params: Mapping[str, Any]) -> ToolResult:
        operation = str(params.get("operation") or "").strip().lower()
        registry = get_registry()

        if operation == "read":
            return self._read_text(params)
        if operation == "search":
            return registry.execute(
                "search_files",
                {
                    "query": params.get("query") or params.get("path"),
                    "directory": params.get("directory"),
                    "kind": params.get("kind"),
                    "open": params.get("open", False),
                },
            )
        if operation in {"open", "locate"}:
            return registry.execute(
                "search_files",
                {
                    "query": params.get("query") or params.get("path"),
                    "directory": params.get("directory"),
                    "kind": params.get("kind", "folder"),
                    "open": True,
                },
            )
        if operation == "list":
            root = params.get("directory") or params.get("path") or "."
            return registry.execute("list_directory", {"directory": root})
        if operation == "create":
            return registry.execute(
                "create_folder",
                {"path": params.get("path") or params.get("directory")},
            )
        if operation == "copy":
            return registry.execute(
                "copy_file",
                {
                    "source": params.get("path") or params.get("source"),
                    "destination": params.get("destination"),
                },
            )
        if operation == "move":
            return registry.execute(
                "move_file",
                {
                    "source": params.get("path") or params.get("source"),
                    "destination": params.get("destination"),
                },
            )
        if operation == "rename":
            return registry.execute(
                "rename_file",
                {
                    "path": params.get("path"),
                    "new_name": params.get("new_name"),
                },
            )
        if operation == "delete":
            return registry.execute("delete_file", {"path": params.get("path")})
        if operation == "count":
            payload: dict[str, Any] = {}
            if params.get("query"):
                payload["query"] = params.get("query")
            if params.get("directory") or params.get("path"):
                payload["directory"] = params.get("directory") or params.get("path")
            if params.get("recursive") is not None:
                payload["recursive"] = params.get("recursive")
            return registry.execute("count_items", payload)

        return ToolResult(
            False,
            "filesystem requires operation: search, list, open, read, create, copy, move, rename, delete, count.",
        )

    def _read_text(self, params: Mapping[str, Any]) -> ToolResult:
        path = str(params.get("path") or "").strip()
        if not path:
            return ToolResult(False, "filesystem read requires path.")
        resolved = os.path.expandvars(os.path.expanduser(path))
        if not os.path.isfile(resolved):
            return ToolResult(False, f"File not found: {resolved}")
        try:
            with open(resolved, "rb") as handle:
                data = handle.read(_MAX_READ_BYTES + 1)
        except OSError as exc:
            return ToolResult(False, f"Could not read file: {exc}")
        truncated = len(data) > _MAX_READ_BYTES
        if truncated:
            data = data[:_MAX_READ_BYTES]
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            return ToolResult(False, "File is not UTF-8 text; binary read is not supported yet.")
        message = text if len(text) < 4000 else text[:3997] + "..."
        extra = {"path": resolved, "truncated": truncated}
        return ToolResult(True, message, extra)
