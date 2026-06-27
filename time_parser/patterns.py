"""Shared regex patterns for time-like phrases in user text."""
from __future__ import annotations

import re

# Matches phrases that indicate a timed reminder rather than a memory task.
TIME_EXPRESSION_RE = re.compile(
    r"\b("
    r"tomorrow|today|tonight|"
    r"at\s+\d|"
    r"in\s+\d+\s+(?:minute|minutes|hour|hours)|"
    r"next\s+\w+|"
    r"every\s+\w+|"
    r"\d{1,2}(?::\d{2})?\s*(?:am|pm)"
    r")\b",
    re.IGNORECASE,
)


def looks_like_timed_reminder(text: str) -> bool:
    """Return True if *text* likely describes a timed reminder, not a task."""
    return bool(text and TIME_EXPRESSION_RE.search(text))
