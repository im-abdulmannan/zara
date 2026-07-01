"""Central registry for all Zara tools."""
from __future__ import annotations

from typing import Any, Mapping, Optional

from tools.base import BaseTool, ToolResult
from tools.domain import (
    CancelReminderTool,
    CreateHabitTool,
    CreateMeetingTool,
    CreateNoteTool,
    DeleteHabitTool,
    ListHabitsTool,
    ListNotesTool,
    ListRemindersTool,
    MarkHabitDoneTool,
    PauseHabitTool,
    QueryCalendarTool,
    QueryMemoryTool,
    RememberTool,
    ResumeHabitTool,
    SearchNotesTool,
    SetReminderTool,
)
from tools.logging_config import get_logger
from tools.registration import registered_tool_classes

_logger = get_logger(__name__)
_modules_loaded = False


def _load_tool_modules() -> None:
    """Import tool modules so :func:`register_tool` decorators run."""
    global _modules_loaded
    if _modules_loaded:
        return
    import tools.applications  # noqa: F401
    import tools.browser  # noqa: F401
    import tools.clipboard  # noqa: F401
    import tools.filesystem  # noqa: F401
    import tools.system  # noqa: F401

    _modules_loaded = True


def _domain_tools() -> list[BaseTool]:
    """Runtime-backed domain tools (registered explicitly)."""
    return [
        RememberTool(),
        SetReminderTool(),
        ListRemindersTool(),
        CancelReminderTool(),
        CreateHabitTool(),
        ListHabitsTool(),
        MarkHabitDoneTool(),
        PauseHabitTool(),
        ResumeHabitTool(),
        DeleteHabitTool(),
        QueryCalendarTool(),
        CreateMeetingTool(),
        CreateNoteTool(),
        SearchNotesTool(),
        ListNotesTool(),
        QueryMemoryTool(),
    ]


def _default_tools() -> list[BaseTool]:
    _load_tool_modules()
    discovered = [cls() for cls in registered_tool_classes()]
    return discovered + _domain_tools()


class ToolRegistry:
    """Maps tool names to executable :class:`BaseTool` instances."""

    def __init__(self, tools: list[BaseTool] | None = None) -> None:
        self._tools: dict[str, BaseTool] = {}
        for tool in tools or _default_tools():
            self.register(tool)

    def register(self, tool: BaseTool) -> None:
        self._tools[tool.name.lower()] = tool
        _logger.debug("Registered tool: %s", tool.name)

    def get(self, name: str) -> Optional[BaseTool]:
        return self._tools.get(name.lower().strip())

    def names(self) -> list[str]:
        return sorted(self._tools.keys())

    def list_tools(self) -> list[dict[str, Any]]:
        """Return JSON-schema metadata for every registered tool."""
        return self.schemas()

    def all_tools(self) -> list[BaseTool]:
        """Return registered tool instances for discovery / plugins."""
        return list(self._tools.values())

    def find_for_intent(self, intent: str) -> list[BaseTool]:
        """Return tools that claim they can handle *intent*."""
        return [tool for tool in self.all_tools() if tool.can_handle(intent)]

    def find_by_intent_text(self, text: str) -> Optional[BaseTool]:
        """Return the best-matching tool whose intent keywords appear in *text*."""
        lowered = (text or "").lower()
        matches: list[tuple[int, BaseTool]] = []
        for tool in self.all_tools():
            for keyword in tool.intent_keywords:
                if keyword in lowered:
                    matches.append((len(keyword), tool))
                    break
        if not matches:
            return None
        matches.sort(key=lambda item: item[0], reverse=True)
        return matches[0][1]

    def schemas(self) -> list[dict[str, Any]]:
        return [tool.schema() for tool in self._tools.values()]

    def build_system_prompt_section(self) -> str:
        """Generate tool documentation for the LLM system prompt."""
        lines = [
            "Available tools — return ONLY valid JSON with a `tool` field.",
            "",
            "For general conversation (no tool needed):",
            '{"tool": "chat", "response": "your answer"}',
            "",
            "For one or more actions, return:",
            '{"tools": [{"tool": "<name>", ...params}, ...], "response": "optional final reply"}',
            "You may also return a single tool as: {\"tool\": \"<name>\", ...params}",
            "",
            "Tool catalog:",
        ]
        for tool in sorted(self._tools.values(), key=lambda t: t.name):
            schema = tool.schema()
            required = ", ".join(schema["required"]) or "none"
            lines.append(f"- {tool.name}: {tool.description}")
            if schema["parameters"]:
                param_desc = "; ".join(
                    f"{name} ({spec['description']})"
                    for name, spec in schema["parameters"].items()
                )
                lines.append(f"  params: {param_desc}")
            lines.append(f"  required: {required}")
            if schema.get("requires_confirmation"):
                lines.append("  requires_confirmation: true")
        return "\n".join(lines)

    def execute(self, name: str, params: Mapping[str, Any] | None = None) -> ToolResult:
        action_name = name.lower().strip()
        tool = self.get(action_name)
        if tool is None:
            _logger.warning("Unknown tool requested: %s", action_name)
            return ToolResult(False, f"Unknown action: {action_name}")

        payload = dict(params or {})
        try:
            _logger.info(
                "Executing tool=%s params=%s requires_confirmation=%s",
                action_name,
                list(payload.keys()),
                tool.requires_confirmation,
            )
            result = tool.execute(payload)
            if result.success:
                _logger.info("Tool %s succeeded: %s", action_name, result.message)
            else:
                _logger.warning("Tool %s failed: %s", action_name, result.message)
            return result
        except Exception as exc:
            _logger.exception("Tool %s raised an exception", action_name)
            return ToolResult(False, f"Failed to execute action {action_name}: {exc}")


_registry: ToolRegistry | None = None


def get_registry() -> ToolRegistry:
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
    return _registry


def execute_tool(action_name: str, tool_data: dict | None = None) -> tuple[bool, str]:
    """Backward-compatible entry point used by legacy callers."""
    result = get_registry().execute(action_name, tool_data)
    return result.as_tuple()
