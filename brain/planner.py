"""Execution planner — LLM proposes actions; tools execute them.

Flow::

    User transcript -> LLM / intent router -> execution plan -> tools -> response

The LLM never calls OS APIs directly. All side effects go through the tool
registry via :func:`tools.executor.execute_plan`.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from agent import ask_agent
from core.guardrails import GuardrailManager
from core.logging_config import get_logger
from core.session import Session
from tools.executor import (
    ExecutionPlan,
    execute_plan,
    extract_tool_calls,
    parse_agent_payload,
    spoken_response,
)
from tools.registry import ToolRegistry, get_registry

_logger = get_logger(__name__)


@dataclass
class PlannerResult:
    """Structured outcome of planning and optional tool execution."""

    raw_agent_response: str
    payload: Dict[str, Any]
    plan: Optional[ExecutionPlan] = None
    spoken_text: str = ""
    used_tools: bool = False
    elapsed_sec: float = 0.0
    awaiting_confirmation: bool = False


@dataclass
class Planner:
    """Turn a user utterance into a spoken response via LLM + tools."""

    registry: ToolRegistry = field(default_factory=get_registry)
    guardrails: GuardrailManager = field(default_factory=GuardrailManager)

    def plan_and_execute(
        self,
        user_text: str,
        session: Session,
    ) -> PlannerResult:
        """Run the full cognition pipeline for one user turn."""
        started = time.monotonic()
        session.current_task = user_text
        session.touch()

        if self.guardrails.has_pending:
            return self._resolve_pending_confirmation(user_text, session, started)

        try:
            raw = ask_agent(user_text)
        except Exception as exc:
            _logger.exception("LLM pipeline failed")
            spoken = str(exc).strip() if isinstance(exc, RuntimeError) else ""
            return PlannerResult(
                raw_agent_response="",
                payload={},
                spoken_text=spoken or "Sorry, I had trouble thinking about that.",
                elapsed_sec=time.monotonic() - started,
            )

        _logger.debug("Agent raw response: %s", raw[:200] if raw else "")

        try:
            payload = parse_agent_payload(raw)
        except Exception:
            _logger.exception("Failed to parse agent JSON")
            return PlannerResult(
                raw_agent_response=raw,
                payload={},
                spoken_text="I didn't understand my own response.",
                elapsed_sec=time.monotonic() - started,
            )

        tool_calls = payload.get("tool") or payload.get("tools")
        is_chat = payload.get("tool") == "chat" or (
            not payload.get("tool") and not payload.get("tools")
        )

        if is_chat:
            text = str(payload.get("response") or "Okay.")
            return PlannerResult(
                raw_agent_response=raw,
                payload=payload,
                spoken_text=text,
                used_tools=False,
                elapsed_sec=time.monotonic() - started,
            )

        if tool_calls:
            risky = self._first_risky_call(payload)
            if risky is not None:
                tool_name = str(risky.get("tool", "")).strip()
                prompt = self.guardrails.request_confirmation(
                    tool_name,
                    dict(risky),
                    full_payload=payload,
                )
                _logger.info("Deferring high-risk tool=%s pending confirmation", tool_name)
                return PlannerResult(
                    raw_agent_response=raw,
                    payload=payload,
                    spoken_text=prompt,
                    used_tools=False,
                    awaiting_confirmation=True,
                    elapsed_sec=time.monotonic() - started,
                )

            return self._execute_payload(raw, payload, session, started)

        return PlannerResult(
            raw_agent_response=raw,
            payload=payload,
            spoken_text="I didn't understand the response.",
            elapsed_sec=time.monotonic() - started,
        )

    def discover_tools_for_intent(self, intent: str) -> list:
        """Return tools that claim they can handle *intent* (plugin hook)."""
        return self.registry.find_for_intent(intent)

    def _resolve_pending_confirmation(
        self,
        user_text: str,
        session: Session,
        started: float,
    ) -> PlannerResult:
        confirmed, action, reply = self.guardrails.evaluate_user_response(user_text)
        if self.guardrails.has_pending:
            return PlannerResult(
                raw_agent_response="",
                payload={},
                spoken_text=reply,
                awaiting_confirmation=True,
                elapsed_sec=time.monotonic() - started,
            )
        if not confirmed or action is None:
            return PlannerResult(
                raw_agent_response="",
                payload={},
                spoken_text=reply,
                elapsed_sec=time.monotonic() - started,
            )

        payload = action.full_payload or {"tool": action.tool_name, **action.arguments}
        result = self._execute_payload("", payload, session, started)
        if not result.spoken_text:
            result.spoken_text = reply
        return result

    def _execute_payload(
        self,
        raw: str,
        payload: Dict[str, Any],
        session: Session,
        started: float,
    ) -> PlannerResult:
        plan = execute_plan(payload, registry=self.registry)
        for step in plan.steps:
            session.record_tool(step.tool, step.success, step.message)
        text = spoken_response(plan, payload)
        return PlannerResult(
            raw_agent_response=raw,
            payload=payload,
            plan=plan,
            spoken_text=text,
            used_tools=True,
            elapsed_sec=time.monotonic() - started,
        )

    def _first_risky_call(self, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        for call in extract_tool_calls(payload):
            tool_name = str(call.get("tool", "")).strip()
            if not tool_name:
                continue
            tool = self.registry.get(tool_name)
            requires = bool(tool.requires_confirmation) if tool is not None else False
            if self.guardrails.needs_confirmation(tool_name, requires_confirmation=requires):
                return call
        return None
