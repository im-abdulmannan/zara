"""Filesystem tools for local file and folder operations."""
from __future__ import annotations

import glob
import os
import re
import shutil
import time
from typing import Any, Mapping, Optional

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

_DRIVE_PATTERNS = (
    re.compile(r"\b(?:on|from|in|at)\s+drive\s*([a-zA-Z])\b", re.I),
    re.compile(r"\bdrive\s*([a-zA-Z])\s*:?", re.I),
    re.compile(r"\b([a-zA-Z])\s+drive\b", re.I),  # "D drive" / "inside D drive"
    re.compile(r"\b(?:on|from|in|at|inside)\s+([a-zA-Z])\s*(?:drive|:)\b", re.I),
    # "on D" / "on D:" / "from D" (common in speech)
    re.compile(r"\b(?:on|from|in|at|inside)\s+([a-zA-Z]):?(?:\s|$|\\)", re.I),
    re.compile(r"\b([a-zA-Z]):(?:\\|(?:\s|$))"),
)

_FIND_TRIGGER_RE = re.compile(
    r"\b(find|locate|search(?:\s+for)?|where\s+is|open)\b",
    re.I,
)

_COUNT_TRIGGER_RE = re.compile(
    r"\b("
    r"how\s+many|"
    r"count|"
    r"number\s+of|"
    r"total\s+(files?|folders?|directories|items?)|"
    r"(view|show|see|give|get|tell).{0,24}\bcount\b|"
    r"count\s+(them|it|that|those|please)"
    r")\b",
    re.I,
)

# Remembers the last count target so follow-ups like "view the count" work.
_last_count_directory: Optional[str] = None

_NAME_STOPWORDS = {
    "the",
    "a",
    "an",
    "my",
    "me",
    "please",
    "for",
    "from",
    "on",
    "in",
    "at",
    "drive",
    "folder",
    "folders",
    "directory",
    "directories",
    "dir",
    "file",
    "files",
    "project",
    "projects",
    "named",
    "called",
    "and",
    "then",
    "open",
    "it",
}


def _resolve_path(path: str) -> str:
    expanded = os.path.expanduser(path.strip())
    return os.path.abspath(expanded)


def _drive_root(letter: str) -> Optional[str]:
    root = f"{letter.upper()}:\\"
    return root if os.path.isdir(root) else None


def extract_drive_letter(text: str) -> Optional[str]:
    """Return a drive letter mentioned in free-form speech/text, if any."""
    for pattern in _DRIVE_PATTERNS:
        match = pattern.search(text or "")
        if match:
            return match.group(1).upper()
    return None


def _strip_drive_phrases(text: str) -> str:
    cleaned = text or ""
    for pattern in _DRIVE_PATTERNS:
        cleaned = pattern.sub(" ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def _infer_kind(text: str) -> str:
    lower = (text or "").lower()
    mentions_folder = any(
        word in lower for word in ("folder", "directory", "dir", "project")
    )
    mentions_file = bool(re.search(r"\bfiles?\b", lower))
    if mentions_folder and not mentions_file:
        return "folder"
    if mentions_file and not mentions_folder:
        return "file"
    return "both"


def _extract_query_name(text: str) -> str:
    """Pull a likely file/folder name out of a find/open utterance."""
    cleaned = _strip_drive_phrases(text or "")
    cleaned = _FIND_TRIGGER_RE.sub(" ", cleaned)
    cleaned = re.sub(
        r"\b(folder|folders|directory|directories|dir|file|files|project|projects)\b",
        " ",
        cleaned,
        flags=re.I,
    )
    cleaned = re.sub(r"[\"'`]", " ", cleaned)
    cleaned = re.sub(r"[^a-zA-Z0-9._\-\s]", " ", cleaned)
    tokens = [
        t
        for t in cleaned.split()
        if t.lower() not in _NAME_STOPWORDS and not re.fullmatch(r"[a-zA-Z]", t)
    ]
    if not tokens:
        return ""
    # Prefer the last content token ("find the zara folder" -> zara)
    return tokens[-1].strip(".-_")


def parse_find_request(user_text: str) -> Optional[dict[str, Any]]:
    """Deterministic parser for find/open file-or-folder voice requests.

    Returns a ``search_files`` tool payload, or ``None`` if the utterance
    does not look like a filesystem find request.
    """
    text = (user_text or "").strip()
    if not text or not _FIND_TRIGGER_RE.search(text):
        return None

    lower = text.lower()
    looks_like_fs = any(
        word in lower
        for word in (
            "folder",
            "directory",
            "file",
            "project",
            "drive",
            "locate",
            "where is",
        )
    ) or bool(extract_drive_letter(text))
    if not looks_like_fs:
        return None

    query = _extract_query_name(text)
    if not query or len(query) < 2:
        return None

    # Plain "open chrome" should stay as an app launch (handled elsewhere).
    if re.match(r"^\s*open\b", lower) and not any(
        word in lower for word in ("folder", "directory", "file", "drive", "where", "locate")
    ):
        # Still allow "open <name>" when it looks like a project/folder name;
        # app launches are decided in brain.reason.
        if " " not in query and query.lower() in {
            "chrome",
            "edge",
            "firefox",
            "notepad",
            "calculator",
            "calc",
            "code",
            "vscode",
            "spotify",
            "discord",
            "explorer",
            "cmd",
            "powershell",
            "terminal",
            "word",
            "excel",
            "outlook",
        }:
            return None

    kind = _infer_kind(text)
    drive = extract_drive_letter(text)
    payload: dict[str, Any] = {
        "tool": "search_files",
        "query": query,
        "kind": kind,
        "open": True,
    }
    if drive:
        root = _drive_root(drive)
        if root:
            payload["directory"] = root
        else:
            payload["directory"] = f"{drive}:\\"
    return payload


def _resolve_directory_arg(raw: Any) -> Optional[str]:
    if raw is None:
        return None
    directory = str(raw).strip()
    if not directory:
        return None
    if re.fullmatch(r"[a-zA-Z]:?", directory):
        directory = f"{directory.rstrip(':').upper()}:\\"
    path = _resolve_path(directory)
    return path if os.path.isdir(path) else None


def _extract_count_folder_name(text: str) -> str:
    """Extract a named folder from count phrases like 'in the zara folder' / 'in zara'."""
    patterns = (
        re.compile(
            r"\b(?:in|inside|within|for)\s+(?:the\s+)?([a-zA-Z0-9._\-]+)\s+"
            r"(?:folder|directory|dir|project)\b",
            re.I,
        ),
        re.compile(
            r"\b(?:the\s+)?([a-zA-Z0-9._\-]+)\s+(?:folder|directory|dir|project)\b",
            re.I,
        ),
        # "how many ... in zara" (folder word omitted)
        re.compile(
            r"\b(?:in|inside|within)\s+(?:the\s+)?([a-zA-Z0-9._\-]{2,})\s*$",
            re.I,
        ),
    )
    for pattern in patterns:
        match = pattern.search(text or "")
        if not match:
            continue
        name = match.group(1).strip(".-_")
        if name.lower() in _NAME_STOPWORDS or re.fullmatch(r"[a-zA-Z]", name):
            continue
        # Don't treat bare drive letters / "drive" leftovers as names.
        if name.lower() in {"drive", "disk"}:
            continue
        return name
    return ""


def parse_count_request(
    user_text: str,
    *,
    recent_text: str = "",
) -> Optional[dict[str, Any]]:
    """Deterministic parser for count file/folder requests.

    Handles:
    - "How many files/folders do I have in drive D"
    - "How many files folders do I have in zara folder?"
    - Follow-ups like "I would like to view the count" using recent context
    """
    text = (user_text or "").strip()
    if not text or not _COUNT_TRIGGER_RE.search(text):
        return None

    lower = text.lower()
    folder_name = _extract_count_folder_name(text)
    drive_in_text = extract_drive_letter(text)
    path_match = re.search(r"\b([a-zA-Z]:\\[^\s\"']+)", text)

    payload: dict[str, Any] = {
        "tool": "count_items",
        "recursive": True,
    }

    if folder_name:
        # Named folder wins over stale drive context from earlier turns.
        payload["query"] = folder_name
        if drive_in_text:
            root = _drive_root(drive_in_text) or f"{drive_in_text}:\\"
            payload["directory"] = root
        recursive = True
    elif path_match:
        payload["directory"] = path_match.group(1)
        recursive = True
    elif drive_in_text:
        payload["directory"] = _drive_root(drive_in_text) or f"{drive_in_text}:\\"
        recursive = True
    elif extract_drive_letter(recent_text) or _last_count_directory:
        # Pure follow-up ("view the count") with no new target in this message.
        drive = extract_drive_letter(recent_text)
        if drive:
            payload["directory"] = _drive_root(drive) or f"{drive}:\\"
        else:
            payload["directory"] = _last_count_directory or ""
        recursive = True
    else:
        payload["directory"] = ""
        recursive = True

    if any(
        word in lower
        for word in ("all", "entire", "whole", "recursive", "including sub", "everything")
    ):
        recursive = True
    if any(
        phrase in lower
        for phrase in ("top level", "top-level", "only in root", "directly in")
    ):
        recursive = False

    payload["recursive"] = recursive
    return payload


def parse_filesystem_request(
    user_text: str,
    *,
    recent_text: str = "",
) -> Optional[dict[str, Any]]:
    """Route local filesystem intents (count first, then find/open)."""
    count_payload = parse_count_request(user_text, recent_text=recent_text)
    if count_payload is not None:
        return count_payload
    return parse_find_request(user_text)


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
    for drive in ("D:\\", "C:\\", "E:\\"):
        if os.path.isdir(drive):
            roots.append(drive)
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


def _truthy(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on", "open"}


def _rank_paths(paths: list[str], query: str) -> list[str]:
    """Prefer exact basename matches, then shallower / shorter paths."""
    needle = query.lower().strip("*? ")

    def score(path: str) -> tuple:
        name = os.path.basename(path).lower()
        if name == needle:
            exact = 0
        elif name.startswith(needle):
            exact = 1
        elif needle in name:
            exact = 2
        else:
            exact = 3
        depth = path.count(os.sep)
        return (exact, depth, len(path), name)

    return sorted(paths, key=score)


def _open_path(path: str) -> None:
    os.startfile(path)  # type: ignore[attr-defined]


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
        _open_path(path)
        return ToolResult(True, f"Opening {path}.", {"path": path})


@register_tool
class ListDirectoryTool(BaseTool):
    name = "list_directory"
    description = (
        "List top-level files and/or folders in a directory or drive. "
        "Use for 'list all folders in D drive'. "
        "Example: {\"tool\":\"list_directory\",\"directory\":\"D:\\\\\",\"kind\":\"folder\"}."
    )
    parameters = (
        ToolParameter("directory", "Directory or drive to list, e.g. D:\\\\"),
        ToolParameter(
            "kind",
            "Optional: file, folder, or both (default both)",
            required=False,
        ),
    )
    intent_keywords = (
        "list folders",
        "list files",
        "show folders",
        "list directory",
    )

    def execute(self, params: Mapping[str, Any]) -> ToolResult:
        directory = _resolve_directory_arg(
            params.get("directory") or params.get("path") or params.get("drive")
        )
        if not directory:
            return ToolResult(
                False,
                "Which drive or folder should I list? For example: drive D.",
            )

        kind = str(params.get("kind") or "both").strip().lower()
        want_files = kind in {"file", "files", "both", "any", ""}
        want_folders = kind in {
            "folder",
            "folders",
            "directory",
            "directories",
            "dir",
            "both",
            "any",
            "",
        }

        folders: list[str] = []
        files: list[str] = []
        try:
            with os.scandir(directory) as entries:
                for entry in entries:
                    try:
                        name = entry.name
                        if entry.is_dir(follow_symlinks=False):
                            if want_folders and not _should_skip_dir(name):
                                folders.append(name)
                        elif entry.is_file(follow_symlinks=False) and want_files:
                            files.append(name)
                    except OSError:
                        continue
        except OSError as exc:
            return ToolResult(False, f"Could not read {directory}: {exc}")

        folders.sort(key=str.lower)
        files.sort(key=str.lower)
        max_show = 40
        parts: list[str] = []
        if want_folders:
            shown = folders[:max_show]
            extra = len(folders) - len(shown)
            folder_text = ", ".join(shown) if shown else "(none)"
            if extra > 0:
                folder_text += f" and {extra} more"
            parts.append(f"{len(folders)} folders: {folder_text}")
        if want_files:
            shown = files[:max_show]
            extra = len(files) - len(shown)
            file_text = ", ".join(shown) if shown else "(none)"
            if extra > 0:
                file_text += f" and {extra} more"
            parts.append(f"{len(files)} files: {file_text}")

        message = f"In {directory}: " + "; ".join(parts) + "."
        return ToolResult(
            True,
            message,
            {
                "directory": directory,
                "folders": folders,
                "files": files,
                "folder_count": len(folders),
                "file_count": len(files),
            },
        )


def _find_best_folder(
    query: str,
    *,
    search_root: Optional[str] = None,
    max_seconds: float = 20.0,
) -> Optional[str]:
    """Locate the best folder match for *query* under optional *search_root*."""
    needle = (query or "").strip()
    if not needle:
        return None

    if search_root:
        root = _resolve_directory_arg(search_root)
        roots = [root] if root else []
    else:
        roots = _default_search_roots()
    if not roots:
        return None

    pattern = needle if ("*" in needle or "?" in needle) else f"*{needle}*"
    pattern_l = pattern.lower()
    matches: list[str] = []
    started = time.monotonic()

    for start_root in roots:
        for root, dirnames, _filenames in os.walk(start_root):
            if time.monotonic() - started > max_seconds:
                break
            dirnames[:] = [d for d in dirnames if not _should_skip_dir(d)]
            for dirname in list(dirnames):
                if glob.fnmatch.fnmatch(dirname.lower(), pattern_l):
                    matches.append(os.path.join(root, dirname))
            if matches and any(
                os.path.basename(path).lower() == needle.lower() for path in matches
            ):
                # Exact name found — good enough, stop early.
                break
        if matches and any(
            os.path.basename(path).lower() == needle.lower() for path in matches
        ):
            break
        if time.monotonic() - started > max_seconds:
            break

    if not matches:
        return None
    return _rank_paths(matches, needle)[0]


@register_tool
class CountItemsTool(BaseTool):
    name = "count_items"
    description = (
        "Count files and folders under a directory, drive, or named folder. "
        "Use for 'how many on drive D' or 'how many in the zara folder'. "
        "Example: {\"tool\":\"count_items\",\"query\":\"zara\",\"recursive\":true}."
    )
    parameters = (
        ToolParameter(
            "directory",
            "Directory or drive to count, e.g. D:\\\\",
            required=False,
        ),
        ToolParameter(
            "query",
            "Folder name to find and count, e.g. zara",
            required=False,
        ),
        ToolParameter(
            "recursive",
            "If true, count nested files/folders too (default true)",
            required=False,
        ),
    )
    intent_keywords = (
        "how many files",
        "how many folders",
        "count files",
        "count folders",
        "number of files",
    )

    def execute(self, params: Mapping[str, Any]) -> ToolResult:
        global _last_count_directory

        query = str(
            params.get("query")
            or params.get("name")
            or params.get("folder")
            or ""
        ).strip()
        directory = _resolve_directory_arg(
            params.get("directory") or params.get("path") or params.get("drive")
        )

        if query:
            # If directory looks like a drive root, treat it as the search scope.
            search_root = directory
            found = _find_best_folder(query, search_root=search_root)
            if not found and search_root:
                # Fall back to common roots if not found under the given drive.
                found = _find_best_folder(query, search_root=None)
            if not found:
                where = search_root or "your common folders"
                return ToolResult(
                    False,
                    f"I couldn't find a folder named {query} under {where}.",
                )
            directory = found
        elif not directory:
            return ToolResult(
                False,
                "Which drive or folder should I count? For example: drive D, or the zara folder.",
            )

        recursive = _truthy(params.get("recursive"), default=True)
        _last_count_directory = directory

        top_files = 0
        top_folders = 0
        try:
            with os.scandir(directory) as entries:
                for entry in entries:
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            if not _should_skip_dir(entry.name):
                                top_folders += 1
                        elif entry.is_file(follow_symlinks=False):
                            top_files += 1
                    except OSError:
                        continue
        except OSError as exc:
            return ToolResult(False, f"Could not read {directory}: {exc}")

        data: dict[str, Any] = {
            "directory": directory,
            "query": query or None,
            "top_level_files": top_files,
            "top_level_folders": top_folders,
            "recursive": recursive,
        }

        if not recursive:
            total = top_files + top_folders
            message = (
                f"In {directory} there are {top_folders} folders and "
                f"{top_files} files at the top level ({total} items)."
            )
            return ToolResult(True, message, data)

        total_files = 0
        total_folders = 0
        started = time.monotonic()
        max_seconds = 45.0
        timed_out = False

        for root, dirnames, filenames in os.walk(directory):
            if time.monotonic() - started > max_seconds:
                timed_out = True
                break
            dirnames[:] = [d for d in dirnames if not _should_skip_dir(d)]
            total_folders += len(dirnames)
            total_files += len(filenames)

        data.update(
            {
                "total_files": total_files,
                "total_folders": total_folders,
                "timed_out": timed_out,
                "elapsed_sec": round(time.monotonic() - started, 2),
            }
        )

        message = (
            f"In {directory}: {top_folders} folders and {top_files} files at the top level. "
            f"Overall I counted {total_folders} folders and {total_files} files"
        )
        if timed_out:
            message += f" before hitting the {int(max_seconds)} second scan limit"
        message += "."
        return ToolResult(True, message, data)


@register_tool
class SearchFilesTool(BaseTool):
    name = "search_files"
    description = (
        "Search for files or folders by name on this computer and open the best "
        "match in File Explorer. Use when the user asks to find/open a project, "
        "folder, or file (e.g. query='zara', directory='D:\\\\', kind='folder', "
        "open=true)."
    )
    parameters = (
        ToolParameter(
            "query",
            "Name or glob pattern to find, e.g. zara, *.pdf, or report",
        ),
        ToolParameter(
            "directory",
            "Optional root directory or drive, e.g. D:\\\\",
            required=False,
        ),
        ToolParameter(
            "kind",
            "Optional: file, folder, or both (default both)",
            required=False,
        ),
        ToolParameter(
            "open",
            "If true (default), open the best match in File Explorer",
            required=False,
        ),
    )
    intent_keywords = (
        "find file",
        "find folder",
        "search files",
        "where is",
        "locate",
        "open folder",
    )

    def execute(self, params: Mapping[str, Any]) -> ToolResult:
        raw_query = (
            params.get("query")
            or params.get("name")
            or params.get("filename")
            or params.get("folder")
            or params.get("pattern")
            or ""
        )
        query = str(raw_query).strip()
        # Allow drive hints inside the query itself.
        drive_in_query = extract_drive_letter(query)
        if drive_in_query:
            query = _extract_query_name(query) or _strip_drive_phrases(query)
        if not query:
            return ToolResult(False, "What file or folder should I search for?")

        kind = str(params.get("kind") or "both").strip().lower()
        want_files = kind in {"file", "files", "both", "any", ""}
        want_folders = kind in {
            "folder",
            "folders",
            "directory",
            "dir",
            "project",
            "both",
            "any",
            "",
        }
        should_open = _truthy(params.get("open"), default=True)

        roots: list[str]
        directory_param = params.get("directory") or params.get("drive")
        if directory_param:
            directory = str(directory_param).strip()
            if re.fullmatch(r"[a-zA-Z]:?", directory):
                directory = f"{directory.rstrip(':').upper()}:\\"
            directory = _resolve_path(directory)
            if not os.path.isdir(directory):
                return ToolResult(False, f"Directory {directory} does not exist.")
            roots = [directory]
        elif drive_in_query:
            root = _drive_root(drive_in_query)
            if not root:
                return ToolResult(
                    False,
                    f"Drive {drive_in_query}: is not available on this computer.",
                )
            roots = [root]
        else:
            roots = _default_search_roots()

        pattern = query if ("*" in query or "?" in query) else f"*{query}*"
        pattern_l = pattern.lower()
        file_matches: list[str] = []
        folder_matches: list[str] = []
        started = time.monotonic()
        max_seconds = 20.0
        max_results = 40

        for start_root in roots:
            for root, dirnames, filenames in os.walk(start_root):
                if time.monotonic() - started > max_seconds:
                    break
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

        folder_matches = _rank_paths(folder_matches, query)
        file_matches = _rank_paths(file_matches, query)
        matches = folder_matches + file_matches

        if not matches:
            where = roots[0] if len(roots) == 1 else "your common project folders"
            return ToolResult(
                True,
                f"I couldn't find anything named {query} under {where}.",
                {"matches": [], "folders": [], "files": [], "opened": None},
            )

        opened: Optional[str] = None
        if should_open:
            target = folder_matches[0] if folder_matches else file_matches[0]
            try:
                _open_path(target)
                opened = target
            except OSError as exc:
                return ToolResult(
                    False,
                    f"Found {target}, but could not open it: {exc}",
                    {
                        "matches": matches[:max_results],
                        "folders": folder_matches[:max_results],
                        "files": file_matches[:max_results],
                        "opened": None,
                    },
                )

        if opened:
            label = "folder" if os.path.isdir(opened) else "file"
            message = f"Opening {label} {opened}."
            if len(matches) > 1:
                message += f" Found {len(matches)} matches; opened the best one."
            return ToolResult(
                True,
                message,
                {
                    "matches": matches[:max_results],
                    "folders": folder_matches[:max_results],
                    "files": file_matches[:max_results],
                    "opened": opened,
                },
            )

        parts: list[str] = []
        if folder_matches:
            parts.append(
                "folders: "
                + "; ".join(folder_matches[:5])
                + (
                    f" and {len(folder_matches) - 5} more"
                    if len(folder_matches) > 5
                    else ""
                )
            )
        if file_matches:
            parts.append(
                "files: "
                + "; ".join(file_matches[:5])
                + (
                    f" and {len(file_matches) - 5} more"
                    if len(file_matches) > 5
                    else ""
                )
            )
        return ToolResult(
            True,
            f"Found {len(matches)} matches for {query}. " + " ".join(parts) + ".",
            {
                "matches": matches[:max_results],
                "folders": folder_matches[:max_results],
                "files": file_matches[:max_results],
                "opened": None,
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
        dest = (
            new_name
            if os.path.isabs(new_name)
            else os.path.join(os.path.dirname(path), new_name)
        )
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
