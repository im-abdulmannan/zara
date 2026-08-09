"""Agent-style understanding step: think about the ask, then choose an action."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Optional

from tools.filesystem import (
    extract_drive_letter,
    parse_count_request,
    parse_find_request,
)


@dataclass
class AgentDecision:
    """Result of the pre-action reasoning step."""

    thought: str
    action: Optional[dict[str, Any]] = None
    use_llm: bool = True


_TIME_RE = re.compile(
    r"\b(what(?:'s|\s+is)\s+the\s+time|what\s+time\s+is\s+it|current\s+time)\b",
    re.I,
)

_EXISTENCE_RE = re.compile(
    r"\b("
    r"do\s+i\s+have|"
    r"is\s+there|"
    r"are\s+there|"
    r"any\s+(?:available|folders?|files?|projects?)|"
    r"available\s+in|"
    r"exist(?:s|ing)?"
    r")\b",
    re.I,
)

_LIST_RE = re.compile(
    r"\b("
    r"list(?:\s+all)?(?:\s+of)?(?:\s+the)?|"
    r"show(?:\s+me)?(?:\s+all)?(?:\s+of)?(?:\s+the)?|"
    r"what(?:'s|\s+are)\s+(?:all\s+)?(?:the\s+)?"
    r")\b.{0,40}\b(folders?|directories|files?|items?)\b",
    re.I,
)

_QUOTED_NAME_RE = re.compile(r"[\"“”']([^\"“”']{1,120})[\"“”']")

_KNOWN_APPS = {
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
}

_NAME_STOPWORDS = {
    "the",
    "a",
    "an",
    "my",
    "me",
    "any",
    "available",
    "some",
    "folder",
    "folders",
    "file",
    "files",
    "directory",
    "directories",
    "project",
    "projects",
    "system",
    "computer",
    "drive",
    "disk",
    "in",
    "on",
    "from",
    "for",
    "of",
    "to",
    "do",
    "i",
    "have",
    "is",
    "are",
    "there",
    "please",
}


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def _recent_search_query(recent_text: str) -> str:
    """Pull the last searched name from recent conversation/tool JSON."""
    text = recent_text or ""
    patterns = (
        re.compile(r'"query"\s*:\s*"([^"]+)"', re.I),
        re.compile(
            r"\b(?:folder|file|project)\s+(?:named\s+)?([a-zA-Z0-9._\-]{2,})\b",
            re.I,
        ),
        re.compile(
            r"\b(?:any|the|a)\s+([a-zA-Z0-9._\-]{2,})\s+(?:folder|file|project)\b",
            re.I,
        ),
        re.compile(
            r"\b(?:search|find|locate|open).*?\b([a-zA-Z0-9._\-]{2,})\b",
            re.I,
        ),
    )
    for pattern in patterns:
        matches = pattern.findall(text)
        for match in reversed(matches):
            name = str(match).strip().lower()
            if name and name not in _NAME_STOPWORDS and not re.fullmatch(r"[a-z]", name):
                return str(match).strip()
    return ""


def _extract_quoted_name(text: str) -> str:
    match = _QUOTED_NAME_RE.search(text or "")
    if not match:
        return ""
    name = match.group(1).strip()
    return name if len(name) >= 2 else ""


def _extract_existence_name(text: str) -> str:
    quoted = _extract_quoted_name(text)
    if quoted:
        return quoted

    patterns = (
        re.compile(
            r"\b(?:any|a|the)\s+([a-zA-Z0-9._\-]{2,})\s+"
            r"(?:folder|directory|dir|project|file)s?\b",
            re.I,
        ),
        re.compile(
            r"\b(?:folder|directory|dir|project|file)s?\s+"
            r"(?:named|called|=|:)?\s*([a-zA-Z0-9._\- ]{2,}?)\s*$",
            re.I,
        ),
        re.compile(
            r"\b([a-zA-Z0-9._\-]{2,})\s+(?:folder|directory|dir|project|file)s?\b",
            re.I,
        ),
    )
    for pattern in patterns:
        match = pattern.search(text or "")
        if not match:
            continue
        name = match.group(1).strip(" .-_")
        if name.lower() in _NAME_STOPWORDS:
            continue
        return name
    return ""


def reason_about_request(
    user_text: str,
    *,
    recent_text: str = "",
) -> AgentDecision:
    """Interpret the user request before any tool runs.

    Returns a human-readable *thought* plus either a concrete tool action
    or ``use_llm=True`` so the main model can finish the plan.
    """
    text = _clean(user_text)
    if not text:
        return AgentDecision(
            thought="Empty request — nothing to do.",
            action={"tool": "chat", "response": "What would you like me to do?"},
            use_llm=False,
        )

    lower = text.lower()

    # --- Time ---
    if _TIME_RE.search(lower):
        return AgentDecision(
            thought="User is asking for the current time, so I should use get_time.",
            action={"tool": "get_time"},
            use_llm=False,
        )

    # --- Count files/folders ---
    count_action = parse_count_request(text, recent_text=recent_text)
    if count_action is not None:
        target = count_action.get("query") or count_action.get("directory") or "that location"
        thought = (
            f"User wants a file/folder count for '{target}'. "
            "I will locate the target if needed, then run count_items."
        )
        return AgentDecision(thought=thought, action=count_action, use_llm=False)

    # --- List folders/files in a drive or directory ---
    list_action = _parse_list_request(text)
    if list_action is not None:
        target = list_action.get("directory") or "that location"
        kind = list_action.get("kind") or "both"
        thought = (
            f"User wants a {kind} listing under {target}. "
            "I will list top-level items there."
        )
        return AgentDecision(thought=thought, action=list_action, use_llm=False)

    # --- Existence / availability checks ("do I have any zara folder…") ---
    existence = _parse_existence_request(text, recent_text=recent_text)
    if existence is not None:
        query = existence.get("query") or "item"
        scope = existence.get("directory") or "the system"
        thought = (
            f"User is asking whether '{query}' exists under {scope}. "
            "I will search without auto-opening Explorer."
        )
        return AgentDecision(thought=thought, action=existence, use_llm=False)

    # --- Find / open / locate folders & files ---
    find_action = parse_find_request(text)
    if find_action is None:
        find_action = _soft_open_or_locate(text)
    if find_action is not None:
        query = find_action.get("query") or "item"
        kind = find_action.get("kind") or "both"
        thought = (
            f"User wants to find/open '{query}' ({kind}). "
            "I will search the filesystem and open the best match."
        )
        return AgentDecision(thought=thought, action=find_action, use_llm=False)

    # --- Drive-only questions without count words ---
    drive = extract_drive_letter(text)
    if drive and any(w in lower for w in ("file", "folder", "directory", "item")):
        return AgentDecision(
            thought=(
                f"User mentioned drive {drive} and files/folders, but the ask is unclear. "
                "I will ask the main model to clarify or choose the right tool."
            ),
            use_llm=True,
        )

    return AgentDecision(
        thought=(
            "No high-confidence local tool match. "
            "I will think with the main model about what the user wants, "
            "then choose a tool or reply."
        ),
        use_llm=True,
    )


def _parse_list_request(text: str) -> Optional[dict[str, Any]]:
    """Handle 'list all folders inside D drive' style asks."""
    lower = text.lower()
    if not _LIST_RE.search(lower):
        return None

    drive = extract_drive_letter(text)
    directory = f"{drive}:\\" if drive else ""
    path_match = re.search(r"\b([a-zA-Z]:\\[^\s\"']+)", text)
    if path_match:
        directory = path_match.group(1)
    if not directory:
        return None

    if re.search(r"\bfolders?\b|\bdirectories\b", lower) and not re.search(
        r"\bfiles?\b", lower
    ):
        kind = "folder"
    elif re.search(r"\bfiles?\b", lower) and not re.search(
        r"\bfolders?\b|\bdirectories\b", lower
    ):
        kind = "file"
    else:
        kind = "both"

    return {
        "tool": "list_directory",
        "directory": directory,
        "kind": kind,
    }


def _parse_existence_request(
    text: str,
    *,
    recent_text: str = "",
) -> Optional[dict[str, Any]]:
    """Handle 'do I have / is there / any available in D drive' style asks."""
    lower = text.lower()
    if not _EXISTENCE_RE.search(lower):
        return None

    drive = extract_drive_letter(text)
    query = _extract_existence_name(text)
    has_explicit_target = bool(query) or bool(_extract_quoted_name(text)) or bool(
        re.search(r"\b(?:folder|directory|file|project)s?\b", lower)
        and _QUOTED_NAME_RE.search(text or "")
    )

    # Follow-up only when this turn is vague ("any available in D?") and
    # does NOT already name a folder/file target.
    vague_followup = (
        not has_explicit_target
        and (
            "available" in lower
            or re.search(r"\b(?:that|those|them|it)\b", lower)
            or re.search(r"\bany\s+available\b", lower)
        )
    )
    if not query and vague_followup:
        query = _recent_search_query(recent_text)

    if not query:
        return None

    kind = "folder"
    if re.search(r"\bfiles?\b", lower) and not re.search(
        r"\b(?:folder|directory|project)s?\b", lower
    ):
        kind = "file"
    action: dict[str, Any] = {
        "tool": "search_files",
        "query": query,
        "kind": kind,
        "open": False,
    }
    if drive:
        action["directory"] = f"{drive}:\\"
    return action


def _soft_open_or_locate(text: str) -> Optional[dict[str, Any]]:
    """Handle short phrases like 'open billboard' / 'locate zara' without rigid keywords."""
    lower = text.lower().strip()

    open_match = re.match(
        r"^\s*open(?:\s+the)?\s+([a-zA-Z0-9._\-]+)(?:\s+(folder|directory|project|file))?\s*$",
        lower,
    )
    if open_match:
        name = open_match.group(1)
        kind_word = open_match.group(2)
        if name in _KNOWN_APPS and not kind_word:
            return {"tool": "open_app", "name": name}
        kind = "file" if kind_word == "file" else "folder"
        return {
            "tool": "search_files",
            "query": name,
            "kind": kind,
            "open": True,
        }

    locate_match = re.match(
        r"^\s*(?:where(?:\s+can\s+i)?\s+)?(?:locate|find|where\s+is)(?:\s+the)?\s+"
        r"([a-zA-Z0-9._\-]+)(?:\s+(folder|directory|project|file))?\s*\??\s*$",
        lower,
    )
    if locate_match:
        name = locate_match.group(1)
        kind_word = locate_match.group(2)
        kind = "file" if kind_word == "file" else ("folder" if kind_word else "both")
        return {
            "tool": "search_files",
            "query": name,
            "kind": kind,
            "open": True,
        }

    return None
