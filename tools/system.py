"""Windows system control tools."""
from __future__ import annotations

import os
import subprocess
from datetime import datetime
from typing import Any, Mapping

from tools.base import BaseTool, ToolParameter, ToolResult
from tools.registration import register_tool


def lock_pc() -> None:
    """Lock the workstation."""
    os.system("rundll32.exe user32.dll,LockWorkStation")


def shutdown_pc() -> None:
    """Shut down the PC in 10 seconds."""
    os.system("shutdown /s /t 10")


def restart_pc() -> None:
    """Restart the PC in 10 seconds."""
    os.system("shutdown /r /t 10")


def get_current_time() -> str:
    """Return the current formatted system time."""
    return datetime.now().strftime("%I:%M %p")


@register_tool
class GetTimeTool(BaseTool):
    name = "get_time"
    description = "Report the current system time."
    parameters: tuple[ToolParameter, ...] = ()
    intent_keywords = ("time", "what time")

    def execute(self, params: Mapping[str, Any]) -> ToolResult:
        current = get_current_time()
        return ToolResult(True, f"The current time is {current}.", {"time": current})


@register_tool
class LockScreenTool(BaseTool):
    name = "lock_pc"
    description = "Lock the Windows workstation."
    parameters: tuple[ToolParameter, ...] = ()
    intent_keywords = ("lock",)

    def execute(self, params: Mapping[str, Any]) -> ToolResult:
        lock_pc()
        return ToolResult(True, "Locking the computer.")


@register_tool
class ShutdownTool(BaseTool):
    name = "shutdown_pc"
    description = "Shut down the computer after a short delay."
    parameters: tuple[ToolParameter, ...] = ()
    requires_confirmation = True
    intent_keywords = ("shutdown", "shut down")

    def execute(self, params: Mapping[str, Any]) -> ToolResult:
        shutdown_pc()
        return ToolResult(True, "Shutting down the computer.")


@register_tool
class RestartTool(BaseTool):
    name = "restart_pc"
    description = "Restart the computer after a short delay."
    parameters: tuple[ToolParameter, ...] = ()
    requires_confirmation = True
    intent_keywords = ("restart", "reboot")

    def execute(self, params: Mapping[str, Any]) -> ToolResult:
        restart_pc()
        return ToolResult(True, "Restarting the computer.")


@register_tool
class SleepPcTool(BaseTool):
    name = "sleep_pc"
    description = "Put the computer to sleep."
    parameters: tuple[ToolParameter, ...] = ()
    intent_keywords = ("sleep", "suspend")

    def execute(self, params: Mapping[str, Any]) -> ToolResult:
        try:
            subprocess.run(
                ["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"],
                check=False,
            )
            return ToolResult(True, "Putting the computer to sleep.")
        except OSError as exc:
            return ToolResult(False, f"Could not sleep the PC: {exc}")


@register_tool
class ControlVolumeTool(BaseTool):
    name = "control_volume"
    description = "Set, raise, or lower the system master volume."
    parameters = (
        ToolParameter("action", "One of: set, up, down, mute, unmute"),
        ToolParameter(
            "level",
            "Target volume 0-100 when action is set",
            required=False,
            type="integer",
        ),
        ToolParameter(
            "step",
            "Percent step for up/down (default 10)",
            required=False,
            type="integer",
        ),
    )

    def execute(self, params: Mapping[str, Any]) -> ToolResult:
        action = (params.get("action") or "").lower().strip()
        if not action:
            return ToolResult(False, "Should I set, raise, lower, mute, or unmute volume?")

        try:
            from tools.volume_control import VolumeController

            volume = VolumeController()
        except ImportError as exc:
            return ToolResult(False, str(exc))
        except Exception as exc:
            return ToolResult(False, f"Volume control failed: {exc}")

        try:
            if action == "mute":
                volume.mute()
                return ToolResult(True, "Volume muted.")
            if action == "unmute":
                volume.unmute()
                return ToolResult(True, "Volume unmuted.")

            step = int(params.get("step") or 10)
            if action == "up":
                level = volume.increase(step)
                return ToolResult(
                    True,
                    f"Volume increased to {level} percent.",
                    {"level": level},
                )
            if action == "down":
                level = volume.decrease(step)
                return ToolResult(
                    True,
                    f"Volume decreased to {level} percent.",
                    {"level": level},
                )
            if action == "set":
                current = volume.get_volume_percent()
                level = volume.set_volume_percent(int(params.get("level", current)))
                return ToolResult(True, f"Volume set to {level} percent.", {"level": level})

            return ToolResult(False, f"Unknown volume action: {action}")
        except Exception as exc:
            return ToolResult(False, f"Volume control failed: {exc}")


@register_tool
class ControlBrightnessTool(BaseTool):
    name = "control_brightness"
    description = "Set or adjust display brightness on supported Windows devices."
    parameters = (
        ToolParameter("action", "One of: set, up, down"),
        ToolParameter(
            "level",
            "Target brightness 0-100 when action is set",
            required=False,
            type="integer",
        ),
        ToolParameter(
            "step",
            "Percent step for up/down (default 10)",
            required=False,
            type="integer",
        ),
    )

    def execute(self, params: Mapping[str, Any]) -> ToolResult:
        action = (params.get("action") or "").lower().strip()
        if not action:
            return ToolResult(False, "Should I set, raise, or lower brightness?")

        try:
            import wmi
        except ImportError:
            return ToolResult(
                False,
                "Brightness control requires the wmi package. Install with: pip install wmi",
            )

        try:
            monitor = wmi.WMI(namespace="root\\wmi").WmiMonitorBrightnessMethods()[0]
            current = wmi.WMI(namespace="root\\wmi").WmiMonitorBrightness()[0].CurrentBrightness
            step = int(params.get("step") or 10)

            if action == "up":
                level = min(100, int(current) + step)
            elif action == "down":
                level = max(0, int(current) - step)
            elif action == "set":
                level = max(0, min(100, int(params.get("level", current))))
            else:
                return ToolResult(False, f"Unknown brightness action: {action}")

            monitor.WmiSetBrightness(level, 0)
            return ToolResult(True, f"Brightness set to {level} percent.", {"level": level})
        except Exception as exc:
            return ToolResult(
                False,
                f"Brightness control is not available on this device: {exc}",
            )


@register_tool
class TakeScreenshotTool(BaseTool):
    name = "take_screenshot"
    description = "Capture a screenshot and save it to the Pictures folder."
    parameters = (
        ToolParameter(
            "filename",
            "Optional filename without path",
            required=False,
        ),
    )

    def execute(self, params: Mapping[str, Any]) -> ToolResult:
        try:
            from PIL import ImageGrab
        except ImportError:
            return ToolResult(
                False,
                "Screenshots require Pillow. Install with: pip install Pillow",
            )

        pictures = os.path.join(os.path.expanduser("~"), "Pictures")
        os.makedirs(pictures, exist_ok=True)
        name = (params.get("filename") or "").strip()
        if not name:
            name = f"zara_screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        if not name.lower().endswith(".png"):
            name += ".png"
        path = os.path.join(pictures, name)

        try:
            ImageGrab.grab().save(path)
            return ToolResult(True, f"Screenshot saved to {path}.", {"path": path})
        except Exception as exc:
            return ToolResult(False, f"Screenshot failed: {exc}")
