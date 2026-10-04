"""System capability — time, power, volume, brightness, screenshot."""
from __future__ import annotations

from typing import Any, ClassVar, Mapping

from tools.base import BaseTool, ToolParameter, ToolResult
from tools.registry import get_registry
from tools.registration import register_tool


@register_tool
class SystemCapabilityTool(BaseTool):
    name = "system"
    description = (
        "Windows system capability: time, lock, sleep, shutdown, restart, "
        "volume, brightness, screenshot."
    )
    is_capability: ClassVar[bool] = True
    parameters = (
        ToolParameter(
            "operation",
            "One of: time, lock, sleep, shutdown, restart, volume, brightness, screenshot",
        ),
        ToolParameter("action", "Sub-action for volume/brightness: set, up, down, mute, unmute", required=False),
        ToolParameter("level", "Level 0-100 for set actions", required=False, type="integer"),
        ToolParameter("step", "Step percent for up/down", required=False, type="integer"),
        ToolParameter("filename", "Screenshot filename", required=False),
    )
    intent_keywords = ("system", "volume", "brightness", "screenshot", "lock pc")

    def execute(self, params: Mapping[str, Any]) -> ToolResult:
        operation = str(params.get("operation") or "").strip().lower()
        registry = get_registry()

        if operation == "time":
            return registry.execute("get_time", {})
        if operation == "lock":
            return registry.execute("lock_pc", {})
        if operation == "sleep":
            return registry.execute("sleep_pc", {})
        if operation == "shutdown":
            return registry.execute("shutdown_pc", {})
        if operation == "restart":
            return registry.execute("restart_pc", {})
        if operation == "volume":
            return registry.execute(
                "control_volume",
                {
                    "action": params.get("action"),
                    "level": params.get("level"),
                    "step": params.get("step"),
                },
            )
        if operation == "brightness":
            return registry.execute(
                "control_brightness",
                {
                    "action": params.get("action"),
                    "level": params.get("level"),
                    "step": params.get("step"),
                },
            )
        if operation == "screenshot":
            return registry.execute("take_screenshot", {"filename": params.get("filename")})

        return ToolResult(
            False,
            "system requires operation: time, lock, sleep, shutdown, restart, volume, brightness, screenshot.",
        )
