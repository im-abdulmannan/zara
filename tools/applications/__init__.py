"""Application control tools."""
from __future__ import annotations

import os
import subprocess
from typing import Any, Mapping

from tools.apps import open_app as _open_app
from tools.base import BaseTool, ToolParameter, ToolResult


class OpenApplicationTool(BaseTool):
    name = "open_app"
    description = "Open a local application on Windows."
    parameters = (
        ToolParameter("app", "Application name, e.g. chrome, vscode, notepad"),
    )

    def execute(self, params: Mapping[str, Any]) -> ToolResult:
        app = (params.get("app") or "").strip()
        if not app:
            return ToolResult(False, "Which application would you like to open?")
        _, display = _open_app(app)
        return ToolResult(True, f"Opening {display}.", {"app": display})


class CloseApplicationTool(BaseTool):
    name = "close_app"
    description = "Close an application by process name or window title."
    parameters = (
        ToolParameter("app", "Process or window name to close, e.g. notepad, chrome"),
    )

    def execute(self, params: Mapping[str, Any]) -> ToolResult:
        app = (params.get("app") or "").strip()
        if not app:
            return ToolResult(False, "Which application should I close?")
        try:
            subprocess.run(
                ["taskkill", "/IM", f"{app}.exe", "/F"],
                check=False,
                capture_output=True,
                text=True,
            )
            return ToolResult(True, f"Closed {app}.", {"app": app})
        except OSError as exc:
            return ToolResult(False, f"Could not close {app}: {exc}")


class SearchInstalledAppsTool(BaseTool):
    name = "search_installed_apps"
    description = "Search Start Menu shortcuts for installed applications."
    parameters = (
        ToolParameter("query", "Partial application name to search for"),
    )

    def execute(self, params: Mapping[str, Any]) -> ToolResult:
        query = (params.get("query") or "").strip().lower()
        if not query:
            return ToolResult(False, "What application should I search for?")

        roots = [
            os.path.join(os.environ.get("ProgramData", ""), "Microsoft", "Windows", "Start Menu", "Programs"),
            os.path.join(os.environ.get("APPDATA", ""), "Microsoft", "Windows", "Start Menu", "Programs"),
        ]
        matches: list[str] = []
        for root in roots:
            if not root or not os.path.isdir(root):
                continue
            for dirpath, _, filenames in os.walk(root):
                for filename in filenames:
                    if not filename.lower().endswith(".lnk"):
                        continue
                    name = os.path.splitext(filename)[0]
                    if query in name.lower():
                        matches.append(name)
        matches = sorted(set(matches))[:10]
        if not matches:
            return ToolResult(True, f"No installed apps matching {query}.", {"matches": []})
        listed = "; ".join(matches)
        return ToolResult(
            True,
            f"Installed apps matching {query}: {listed}.",
            {"matches": matches},
        )
