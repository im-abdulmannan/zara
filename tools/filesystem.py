"""Filesystem tools for local file and folder operations."""
from __future__ import annotations

import glob
import os
import shutil
import time
from typing import Any, Mapping

from tools.base import BaseTool, ToolParameter, ToolResult
from tools.registration import register_tool

_SKIP_DIR_NAMES = {
    "$recycle.bin",
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    "appdata",
    "application data",
    "local settings",
    "windows",
    "program files",
    "program files (x86)",
    "programdata",
    "system volume information",
}


def _resolve_path(path: str) -> str:
    expanded = os.path.expanduser(path.strip())
    return os.path.abspath(expanded)


def _default_search_roots() -> list[str]:
    """Prefer common user/project locations over a full-disk crawl."""
    home = os.path.expanduser("~")
    roots = [
        home,
        os.path.join(home, "Documents"),
        os.path.join(home, "Desktop"),
        os.path.join(home, "Downloads"),
        os.path.join(home, "source"),
        os.path.join(home, "projects"),
        os.path.join(home, "dev"),
    ]
    # Common Windows drive roots for project folders.
    for drive in ("D:\\", "C:\\", "E:\\"):
        if os.path.isdir(drive):
            roots.append(drive)
    # Deduplicate while preserving order.
    seen: set[str] = set()
    ordered: list[str] = []
    for root in roots:
        path = os.path.abspath(root)
        key = path.lower()
        if key in seen or not os.path.isdir(path):
            continue
        seen.add(key)
        ordered.append(path)
    return ordered


def _should_skip_dir(name: str) -> bool:
    return name.lower() in _SKIP_DIR_NAMES


@register_tool
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


@register_tool
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


@register_tool
class SearchFilesTool(BaseTool):
    name = "search_files"
    description = (
        "Search for files or folders by name on this computer. "
        "Use when the user asks to find a project, folder, or file "
        "(e.g. query='zara'). Searches home, Documents, Desktop, and common drives."
    )
    parameters = (
        ToolParameter(
            "query",
            "Name or glob pattern to find, e.g. zara, *.pdf, or report",
        ),
        ToolParameter(
            "directory",
            "Optional root directory; omit to search common locations",
            required=False,
        ),
        ToolParameter(
            "kind",
            "Optional: file, folder, or both (default both)",
            required=False,
        ),
    )
    intent_keywords = ("find file", "find folder", "search files", "where is", "locate")

    def execute(self, params: Mapping[str, Any]) -> ToolResult:
        query = (
            params.get("query")
            or params.get("name")
            or params.get("filename")
            or params.get("folder")
            or params.get("pattern")
            or ""
        )
        query = str(query).strip()
        if not query:
            return ToolResult(False, "What file or folder should I search for?")

        kind = str(params.get("kind") or "both").strip().lower()
        want_files = kind in {"file", "files", "both", "any", ""}
        want_folders = kind in {"folder", "folders", "directory", "dir", "project", "both", "any", ""}

        roots: list[str]
        if params.get("directory"):
            directory = _resolve_path(str(params.get("directory") or ""))
            if not os.path.isdir(directory):
                return ToolResult(False, f"Directory {directory} does not exist.")
            roots = [directory]
        else:
            roots = _default_search_roots()

        pattern = query if ("*" in query or "?" in query) else f"*{query}*"
        pattern_l = pattern.lower()
        file_matches: list[str] = []
        folder_matches: list[str] = []
        started = time.monotonic()
        max_seconds = 12.0
        max_results = 20

        for start_root in roots:
            for root, dirnames, filenames in os.walk(start_root):
                if time.monotonic() - started > max_seconds:
                    break
                # Prune heavy / system directories in-place.
                dirnames[:] = [d for d in dirnames if not _should_skip_dir(d)]

                if want_folders:
                    for dirname in list(dirnames):
                        if glob.fnmatch.fnmatch(dirname.lower(), pattern_l):
                            folder_matches.append(os.path.join(root, dirname))
                            if len(folder_matches) + len(file_matches) >= max_results:
                                break

                if want_files and len(folder_matches) + len(file_matches) < max_results:
                    for filename in filenames:
                        if glob.fnmatch.fnmatch(filename.lower(), pattern_l):
                            file_matches.append(os.path.join(root, filename))
                            if len(folder_matches) + len(file_matches) >= max_results:
                                break

                if len(folder_matches) + len(file_matches) >= max_results:
                    break
            if len(folder_matches) + len(file_matches) >= max_results:
                break
            if time.monotonic() - started > max_seconds:
                break

        matches = folder_matches + file_matches
        if not matches:
            where = roots[0] if len(roots) == 1 else "your common project folders"
            return ToolResult(
                True,
                f"I couldn't find anything named {query} under {where}.",
                {"matches": [], "folders": [], "files": []},
            )

        parts: list[str] = []
        if folder_matches:
            parts.append(
                "folders: " + "; ".join(folder_matches[:5])
                + (f" and {len(folder_matches) - 5} more" if len(folder_matches) > 5 else "")
            )
        if file_matches:
            parts.append(
                "files: " + "; ".join(file_matches[:5])
                + (f" and {len(file_matches) - 5} more" if len(file_matches) > 5 else "")
            )
        return ToolResult(
            True,
            f"Found {len(matches)} matches for {query}. " + " ".join(parts) + ".",
            {
                "matches": matches[:max_results],
                "folders": folder_matches[:max_results],
                "files": file_matches[:max_results],
            },
        )


@register_tool
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


@register_tool
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


@register_tool
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


@register_tool
class DeleteFileTool(BaseTool):
    name = "delete_file"
    description = "Delete a file or folder."
    parameters = (
        ToolParameter("path", "Path to delete"),
    )
    requires_confirmation = True
    intent_keywords = ("delete file", "delete folder", "remove file")

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
