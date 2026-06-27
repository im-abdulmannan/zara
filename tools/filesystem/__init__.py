"""Filesystem tools for local file and folder operations."""
from __future__ import annotations

import glob
import os
import shutil
from typing import Any, Mapping

from tools.base import BaseTool, ToolParameter, ToolResult


def _resolve_path(path: str) -> str:
    expanded = os.path.expanduser(path.strip())
    return os.path.abspath(expanded)


class CreateFolderTool(BaseTool):
    name = "create_folder"
    description = "Create a folder at the given path."
    parameters = (
        ToolParameter("path", "Folder path to create, e.g. ~/Documents/AI Projects"),
    )

    def execute(self, params: Mapping[str, Any]) -> ToolResult:
        path = _resolve_path(params.get("path") or "")
        if not path:
            return ToolResult(False, "Which folder should I create?")
        try:
            os.makedirs(path, exist_ok=True)
            return ToolResult(True, f"Created folder {path}.", {"path": path})
        except OSError as exc:
            return ToolResult(False, f"Could not create folder: {exc}")


class OpenFolderTool(BaseTool):
    name = "open_folder"
    description = "Open a folder in File Explorer."
    parameters = (
        ToolParameter("path", "Folder path to open"),
    )

    def execute(self, params: Mapping[str, Any]) -> ToolResult:
        path = _resolve_path(params.get("path") or "")
        if not path:
            return ToolResult(False, "Which folder should I open?")
        if not os.path.isdir(path):
            return ToolResult(False, f"Folder {path} does not exist.")
        os.startfile(path)  # type: ignore[attr-defined]
        return ToolResult(True, f"Opening {path}.", {"path": path})


class SearchFilesTool(BaseTool):
    name = "search_files"
    description = "Search for files by name pattern under a directory."
    parameters = (
        ToolParameter("query", "Filename or glob pattern, e.g. *.pdf or report"),
        ToolParameter(
            "directory",
            "Directory to search (defaults to user home)",
            required=False,
        ),
    )

    def execute(self, params: Mapping[str, Any]) -> ToolResult:
        query = (params.get("query") or "").strip()
        if not query:
            return ToolResult(False, "What file should I search for?")
        directory = _resolve_path(params.get("directory") or "~")
        if not os.path.isdir(directory):
            return ToolResult(False, f"Directory {directory} does not exist.")

        pattern = query if ("*" in query or "?" in query) else f"*{query}*"
        matches: list[str] = []
        for root, _, filenames in os.walk(directory):
            for filename in filenames:
                if glob.fnmatch.fnmatch(filename.lower(), pattern.lower()):
                    matches.append(os.path.join(root, filename))
            if len(matches) >= 20:
                break

        if not matches:
            return ToolResult(True, f"No files matching {query} in {directory}.", {"matches": []})
        listed = "; ".join(matches[:5])
        suffix = f" and {len(matches) - 5} more" if len(matches) > 5 else ""
        return ToolResult(
            True,
            f"Found {len(matches)} files: {listed}{suffix}.",
            {"matches": matches[:20]},
        )


class RenameFileTool(BaseTool):
    name = "rename_file"
    description = "Rename a file or folder."
    parameters = (
        ToolParameter("path", "Current path"),
        ToolParameter("new_name", "New filename or full new path"),
    )

    def execute(self, params: Mapping[str, Any]) -> ToolResult:
        path = _resolve_path(params.get("path") or "")
        new_name = (params.get("new_name") or "").strip()
        if not path or not new_name:
            return ToolResult(False, "I need the current path and the new name.")
        if not os.path.exists(path):
            return ToolResult(False, f"{path} does not exist.")
        dest = new_name if os.path.isabs(new_name) else os.path.join(os.path.dirname(path), new_name)
        try:
            os.rename(path, dest)
            return ToolResult(True, f"Renamed to {dest}.", {"path": dest})
        except OSError as exc:
            return ToolResult(False, f"Rename failed: {exc}")


class MoveFileTool(BaseTool):
    name = "move_file"
    description = "Move a file or folder to another location."
    parameters = (
        ToolParameter("source", "Source path"),
        ToolParameter("destination", "Destination path or folder"),
    )

    def execute(self, params: Mapping[str, Any]) -> ToolResult:
        source = _resolve_path(params.get("source") or params.get("path") or "")
        destination = _resolve_path(params.get("destination") or "")
        if not source or not destination:
            return ToolResult(False, "I need a source and destination.")
        if not os.path.exists(source):
            return ToolResult(False, f"{source} does not exist.")
        if os.path.isdir(destination):
            destination = os.path.join(destination, os.path.basename(source))
        try:
            shutil.move(source, destination)
            return ToolResult(True, f"Moved to {destination}.", {"path": destination})
        except OSError as exc:
            return ToolResult(False, f"Move failed: {exc}")


class CopyFileTool(BaseTool):
    name = "copy_file"
    description = "Copy a file or folder to another location."
    parameters = (
        ToolParameter("source", "Source path"),
        ToolParameter("destination", "Destination path or folder"),
    )

    def execute(self, params: Mapping[str, Any]) -> ToolResult:
        source = _resolve_path(params.get("source") or params.get("path") or "")
        destination = _resolve_path(params.get("destination") or "")
        if not source or not destination:
            return ToolResult(False, "I need a source and destination.")
        if not os.path.exists(source):
            return ToolResult(False, f"{source} does not exist.")
        try:
            if os.path.isdir(source):
                if os.path.isdir(destination):
                    destination = os.path.join(destination, os.path.basename(source))
                shutil.copytree(source, destination, dirs_exist_ok=True)
            else:
                if os.path.isdir(destination):
                    destination = os.path.join(destination, os.path.basename(source))
                shutil.copy2(source, destination)
            return ToolResult(True, f"Copied to {destination}.", {"path": destination})
        except OSError as exc:
            return ToolResult(False, f"Copy failed: {exc}")


class DeleteFileTool(BaseTool):
    name = "delete_file"
    description = "Delete a file or folder."
    parameters = (
        ToolParameter("path", "Path to delete"),
    )

    def execute(self, params: Mapping[str, Any]) -> ToolResult:
        path = _resolve_path(params.get("path") or "")
        if not path:
            return ToolResult(False, "Which file or folder should I delete?")
        if not os.path.exists(path):
            return ToolResult(False, f"{path} does not exist.")
        try:
            if os.path.isdir(path):
                shutil.rmtree(path)
            else:
                os.remove(path)
            return ToolResult(True, f"Deleted {path}.", {"path": path})
        except OSError as exc:
            return ToolResult(False, f"Delete failed: {exc}")
