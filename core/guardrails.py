"""Confirmation Safety Guardrails for high-risk system & filesystem operations."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Set


HIGH_RISK_TOOLS: Set[str] = {
    "delete_file",
    "shutdown_pc",
    "restart_pc",
}

CONFIRMATION_ACCEPT_PHRASES = {
    "yes",
    "yeah",
    "yep",
    "confirm",
    "proceed",
    "do it",
    "sure",
    "ok",
    "okay",
}
CONFIRMATION_REJECT_PHRASES = {
    "no",
    "nope",
    "cancel",
    "stop",
    "abort",
    "don't",
    "dont",
}


def _normalize_response(text: str) -> str:
    cleaned = (text or "").lower().strip()
    cleaned = cleaned.replace("\u2019", "'").replace("\u2018", "'")
    return cleaned


def _phrase_matches(text: str, phrases: Set[str]) -> bool:
    """Match whole words/phrases only (avoids 'no' in 'now', 'yes' in 'yesterday')."""
    normalized = _normalize_response(text)
    if not normalized:
        return False
    for phrase in phrases:
        pattern = r"(?<!\w)" + re.escape(phrase.lower()) + r"(?!\w)"
        if re.search(pattern, normalized):
            return True
    return False


@dataclass
class PendingAction:
    """A high-risk tool action awaiting user confirmation."""

    tool_name: str
    arguments: Dict[str, Any]
    prompt_message: str
    full_payload: Dict[str, Any] = field(default_factory=dict)


class GuardrailManager:
    """Manages safety checks and confirmation states for high-risk operations."""

    def __init__(self, high_risk_tools: Set[str] | None = None) -> None:
        self._pending: Optional[PendingAction] = None
        self._high_risk_tools = {name.lower() for name in (high_risk_tools or HIGH_RISK_TOOLS)}

    @property
    def has_pending(self) -> bool:
        return self._pending is not None

    @property
    def pending_action(self) -> Optional[PendingAction]:
        return self._pending

    def is_high_risk(self, tool_name: str) -> bool:
        """Check if a tool requires explicit safety confirmation."""
        return tool_name.lower().strip() in self._high_risk_tools

    def needs_confirmation(
        self,
        tool_name: str,
        *,
        requires_confirmation: bool = False,
    ) -> bool:
        """True when the tool is high-risk or marked ``requires_confirmation``."""
        return requires_confirmation or self.is_high_risk(tool_name)

    def request_confirmation(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        *,
        full_payload: Dict[str, Any] | None = None,
    ) -> str:
        """Set a pending high-risk action and return confirmation query prompt."""
        target = arguments.get("path") or arguments.get("target") or tool_name
        message = (
            f"This will run {tool_name} on {target}. "
            "Say yes to confirm, or no to cancel."
        )
        self._pending = PendingAction(
            tool_name=tool_name,
            arguments=arguments,
            prompt_message=message,
            full_payload=dict(full_payload or {"tool": tool_name, **arguments}),
        )
        return message

    def evaluate_user_response(self, text: str) -> tuple[bool, Optional[PendingAction], str]:
        """Evaluate if user text confirms or cancels the pending high-risk action.

        Returns: (is_confirmed, pending_action|None, reply)
        """
        if not self._pending:
            return False, None, "No action pending confirmation."

        pending = self._pending
        accepted = _phrase_matches(text, CONFIRMATION_ACCEPT_PHRASES)
        rejected = _phrase_matches(text, CONFIRMATION_REJECT_PHRASES)

        # Prefer cancel when both appear — safer default for high-risk tools.
        if rejected:
            self._pending = None
            return False, None, f"Okay, I canceled {pending.tool_name}."
        if accepted:
            self._pending = None
            return True, pending, f"Confirmed. Executing {pending.tool_name}."

        # Ambiguous — keep pending
        return False, None, "Please say yes to confirm or no to cancel."

    def clear(self) -> None:
        self._pending = None
