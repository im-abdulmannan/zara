"""Application capability — open, close, search installed apps."""
from __future__ import annotations

from typing import Any, ClassVar, Mapping

from tools.base import BaseTool, ToolParameter, ToolResult
from tools.registry import get_registry
from tools.registration import register_tool


@register_tool
class ApplicationCapabilityTool(BaseTool):
    name = "application"
    description = (
        "Application capability: open an app, close an app, or search installed apps."
    )
    is_capability: ClassVar[bool] = True
    parameters = (
        ToolParameter(
            "operation",
            "One of: open, close, search",
        ),
        ToolParameter("app", "Application name (open/close)", required=False),
        ToolParameter("query", "Search query for installed apps", required=False),
    )
    intent_keywords = ("open app", "launch", "close app", "installed apps")

    def execute(self, params: Mapping[str, Any]) -> ToolResult:
        operation = str(params.get("operation") or "").strip().lower()
        registry = get_registry()
        app = params.get("app") or params.get("app_name") or params.get("name")

        if operation == "open":
            return registry.execute("open_app", {"app": app})
        if operation == "close":
            return registry.execute("close_app", {"app": app})
        if operation == "search":
            return registry.execute(
                "search_installed_apps",
                {"query": params.get("query") or app},
            )

        return ToolResult(
            False,
            "application requires operation: open, close, search.",
        )
