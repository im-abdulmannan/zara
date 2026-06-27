"""Windows system control tools."""
from __future__ import annotations

import os
import subprocess
from datetime import datetime
from typing import Any, Mapping

from tools.base import BaseTool, ToolParameter, ToolResult
from tools.system_commands import (
    get_current_time as _get_current_time,
    lock_pc as _lock_pc,
    restart_pc as _restart_pc,
    shutdown_pc as _shutdown_pc,
)


class GetTimeTool(BaseTool):
    name = "get_time"
    description = "Report the current system time."
    parameters: tuple = ()

    def execute(self, params: Mapping[str, Any]) -> ToolResult:
        current = _get_current_time()
        return ToolResult(True, f"The current time is {current}.", {"time": current})


class LockScreenTool(BaseTool):
    name = "lock_pc"
    description = "Lock the Windows workstation."
    parameters: tuple = ()

    def execute(self, params: Mapping[str, Any]) -> ToolResult:
        _lock_pc()
        return ToolResult(True, "Locking the computer.")


class ShutdownPcTool(BaseTool):
    name = "shutdown_pc"
    description = "Shut down the computer after a short delay."
    parameters: tuple = ()

    def execute(self, params: Mapping[str, Any]) -> ToolResult:
        _shutdown_pc()
        return ToolResult(True, "Shutting down the computer.")


class RestartPcTool(BaseTool):
    name = "restart_pc"
    description = "Restart the computer after a short delay."
    parameters: tuple = ()

    def execute(self, params: Mapping[str, Any]) -> ToolResult:
        _restart_pc()
        return ToolResult(True, "Restarting the computer.")


class SleepPcTool(BaseTool):
    name = "sleep_pc"
    description = "Put the computer to sleep."
    parameters: tuple = ()

    def execute(self, params: Mapping[str, Any]) -> ToolResult:
        try:
            subprocess.run(
                ["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"],
                check=False,
            )
            return ToolResult(True, "Putting the computer to sleep.")
        except OSError as exc:
            return ToolResult(False, f"Could not sleep the PC: {exc}")


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
            from ctypes import cast, POINTER
            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        except ImportError:
            return ToolResult(
                False,
                "Volume control requires the pycaw package. Install with: pip install pycaw comtypes",
            )

        try:
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = cast(interface, POINTER(IAudioEndpointVolume))
            current = int(round(volume.GetMasterVolumeLevelScalar() * 100))

            if action == "mute":
                volume.SetMute(1, None)
                return ToolResult(True, "Volume muted.")
            if action == "unmute":
                volume.SetMute(0, None)
                return ToolResult(True, "Volume unmuted.")

            step = int(params.get("step") or 10)
            if action == "up":
                level = min(100, current + step)
            elif action == "down":
                level = max(0, current - step)
            elif action == "set":
                level = int(params.get("level", current))
                level = max(0, min(100, level))
            else:
                return ToolResult(False, f"Unknown volume action: {action}")

            volume.SetMasterVolumeLevelScalar(level / 100.0, None)
            return ToolResult(True, f"Volume set to {level} percent.", {"level": level})
        except Exception as exc:
            return ToolResult(False, f"Volume control failed: {exc}")


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


class ClipboardManagerTool(BaseTool):
    name = "clipboard_manager"
    description = "Read from or write to the system clipboard."
    parameters = (
        ToolParameter("action", "One of: read, write"),
        ToolParameter("text", "Text to copy when action is write", required=False),
    )

    def execute(self, params: Mapping[str, Any]) -> ToolResult:
        action = (params.get("action") or "").lower().strip()
        if action == "read":
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
                if not data:
                    return ToolResult(True, "The clipboard is empty.", {"text": ""})
                preview = data[:200] + ("..." if len(data) > 200 else "")
                return ToolResult(True, f"Clipboard contains: {preview}", {"text": data})
            except Exception as exc:
                return ToolResult(False, f"Could not read clipboard: {exc}")

        if action == "write":
            text = params.get("text")
            if text is None:
                return ToolResult(False, "What should I copy to the clipboard?")
            try:
                import win32clipboard

                win32clipboard.OpenClipboard()
                try:
                    win32clipboard.EmptyClipboard()
                    win32clipboard.SetClipboardText(str(text))
                finally:
                    win32clipboard.CloseClipboard()
                return ToolResult(True, "Copied to clipboard.", {"text": str(text)})
            except Exception as exc:
                return ToolResult(False, f"Could not write clipboard: {exc}")

        return ToolResult(False, "Clipboard action must be read or write.")
