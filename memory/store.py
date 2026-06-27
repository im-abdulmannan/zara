import json
import os
import re
from typing import Dict, List

from memories import Memory, list_memories
from time_parser.patterns import looks_like_timed_reminder

_DIR = os.path.dirname(__file__)

SHORT_TERM_FILE = os.path.join(_DIR, "short_term.json")
LONG_TERM_FILE = os.path.join(_DIR, "long_term.json")

# Long term = facts that persist forever (name, preferences).
# Short term = working memory for the current period (ongoing tasks,
# recent context). It is truncated so it never grows without bound.
DEFAULT_LONG_TERM = {
    "user": {
        "name": None,
        "preferences": {}
    },
    "facts": []
}

DEFAULT_SHORT_TERM = {
    "ongoing_tasks": [],
    "context": []
}


def _memory_key(value):
    """Builds a stable key for free-form facts."""
    cleaned = re.sub(r"[^a-z0-9]+", "_", str(value).lower()).strip("_")
    return cleaned[:80] or "fact"


def _memories_by_category(category: str) -> List[Memory]:
    return list_memories(category=category)


def _memory_service():
    """Return the runtime-injected memory service (composition root)."""
    from runtime import get_runtime

    return get_runtime().memory_service


def _load(path, default):
    """Loads JSON from path, falling back to a copy of default."""
    if not os.path.exists(path):
        return json.loads(json.dumps(default))
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading memory {os.path.basename(path)}: {e}")
        return json.loads(json.dumps(default))


def _save(path, data):
    """Writes data to path as pretty JSON."""
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving memory {os.path.basename(path)}: {e}")


# ---------------------------------------------------------------------------
# Long term memory
# ---------------------------------------------------------------------------
def load_long_term():
    """Returns the legacy long-term memory shape, sourced from SQLite."""
    name = None
    for memory in _memories_by_category("user"):
        if memory.key == "name":
            name = memory.value
            break

    preferences: Dict[str, str] = {
        memory.key: memory.value for memory in _memories_by_category("preference")
    }
    facts = [memory.value for memory in _memories_by_category("fact")]

    return {
        "user": {
            "name": name,
            "preferences": preferences,
        },
        "facts": facts,
    }


def save_long_term(data):
    """Migrates a legacy long-term memory payload into SQLite."""
    if not isinstance(data, dict):
        return

    user = data.get("user", {})
    name = user.get("name")
    if name:
        _memory_service().remember("name", name, category="user")

    for key, value in user.get("preferences", {}).items():
        _memory_service().remember(str(key), str(value), category="preference")

    for fact in data.get("facts", []):
        _memory_service().remember(_memory_key(fact), str(fact), category="fact")


def remember_name(name):
    """Stores the user's name permanently."""
    _memory_service().remember("name", name, category="user")


def get_name():
    return load_long_term().get("user", {}).get("name")


def set_preference(key, value):
    """Stores a single user preference, e.g. ('browser', 'chrome')."""
    _memory_service().remember(str(key), str(value), category="preference")


def get_preferences():
    return load_long_term().get("user", {}).get("preferences", {})


def add_fact(fact):
    """Appends a durable fact about the user or world (no duplicates)."""
    _memory_service().remember(_memory_key(fact), str(fact), category="fact")


# ---------------------------------------------------------------------------
# Short term memory
# ---------------------------------------------------------------------------
def load_short_term():
    return _load(SHORT_TERM_FILE, DEFAULT_SHORT_TERM)


def save_short_term(data, max_items=20):
    """Saves short term memory, trimming each list to the most recent items."""
    for key in ("ongoing_tasks", "context"):
        items = data.get(key, [])
        if len(items) > max_items:
            data[key] = items[-max_items:]
    _save(SHORT_TERM_FILE, data)


def add_task(task):
    """Records an ongoing task (no duplicates)."""
    data = load_short_term()
    tasks = data.setdefault("ongoing_tasks", [])
    if task not in tasks:
        tasks.append(task)
    save_short_term(data)


def complete_task(task):
    """Removes a task once it is finished."""
    data = load_short_term()
    tasks = data.setdefault("ongoing_tasks", [])
    if task in tasks:
        tasks.remove(task)
    save_short_term(data)


def get_tasks():
    return load_short_term().get("ongoing_tasks", [])


def add_context(note):
    """Adds a transient note to short term context."""
    data = load_short_term()
    data.setdefault("context", []).append(note)
    save_short_term(data)


def clear_short_term():
    """Wipes working memory (e.g. at the start of a new session)."""
    save_short_term(json.loads(json.dumps(DEFAULT_SHORT_TERM)))


# ---------------------------------------------------------------------------
# Prompt helper
# ---------------------------------------------------------------------------
def memory_summary():
    """Builds a compact text block to inject into the system prompt so the
    model is aware of what Zara already knows about the user."""
    lt = load_long_term()
    st = load_short_term()

    lines = []

    name = lt.get("user", {}).get("name")
    if name:
        lines.append(f"User's name: {name}")

    prefs = lt.get("user", {}).get("preferences", {})
    if prefs:
        pref_text = ", ".join(f"{k}={v}" for k, v in prefs.items())
        lines.append(f"Preferences: {pref_text}")

    facts = lt.get("facts", [])
    if facts:
        lines.append("Known facts: " + "; ".join(facts))

    tasks = st.get("ongoing_tasks", [])
    if tasks:
        lines.append("Ongoing tasks: " + "; ".join(tasks))

    if not lines:
        return "No stored memory about the user yet."

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Deterministic capture
# ---------------------------------------------------------------------------
# Small models rarely emit the "remember" tool reliably, so we also scan the
# raw user text for clear, conservative patterns and write to memory directly.
# Each pattern captures the value in group 1.
_NAME_PATTERNS = [
    re.compile(r"\bmy name is\s+([A-Za-z][\w'\-]*(?:\s+[A-Za-z][\w'\-]*)?)", re.I),
    re.compile(r"\bcall me\s+([A-Za-z][\w'\-]*(?:\s+[A-Za-z][\w'\-]*)?)", re.I),
]
_TASK_PATTERNS = [
    re.compile(r"\bremind me to\s+(.+)", re.I),
    re.compile(r"\bi (?:need|have) to\s+(.+)", re.I),
    re.compile(r"\badd (?:a )?task\s+(?:to\s+)?(.+)", re.I),
]
_PREF_PATTERN = re.compile(r"\bi (?:prefer|like)\s+(.+)", re.I)
_REMEMBER_PATTERN = re.compile(r"\bremember (?:that\s+)?(.+)", re.I)


_JUNK_VALUES = {
    "it", "that", "this", "me", "you", "him", "her", "them", "us",
    "i", "a", "an", "the", "to", "do", "ok", "okay", "yes", "no",
}


def _clean(value):
    """Trims trailing punctuation/whitespace from a captured phrase."""
    return value.strip().strip(".!?,").strip()


def _is_junk(value):
    """True if a captured phrase is too short or a meaningless stopword."""
    if not value or len(value) < 3:
        return True
    return value.lower() in _JUNK_VALUES


def auto_capture(text):
    """Scans raw user text for memory-worthy statements and saves them.

    Returns a list of human-readable confirmations for anything captured,
    so the caller can acknowledge it. Runs independently of the LLM.
    """
    captured = []
    if not text:
        return captured

    for pattern in _NAME_PATTERNS:
        match = pattern.search(text)
        if match:
            name = _clean(match.group(1)).title()
            current = get_name() or ""
            if name and name.lower() != current.lower():
                remember_name(name)
                captured.append(f"your name is {name}")
            break

    for pattern in _TASK_PATTERNS:
        match = pattern.search(text)
        if match:
            # Timed reminders belong in the reminder system, not short-term tasks.
            if looks_like_timed_reminder(text):
                break
            task = _clean(match.group(1))
            if not _is_junk(task) and task not in get_tasks():
                add_task(task)
                captured.append(f"task: {task}")
            break

    pref = _PREF_PATTERN.search(text)
    if pref:
        value = _clean(pref.group(1))
        if not _is_junk(value):
            add_fact(f"prefers {value}")
            captured.append(f"you prefer {value}")

    remember = _REMEMBER_PATTERN.search(text)
    if remember:
        fact = _clean(remember.group(1))
        if not _is_junk(fact):
            add_fact(fact)
            captured.append(fact)

    return captured
