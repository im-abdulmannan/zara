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

from brain.agent import ask_agent
from core.logging_config import get_logger
from core.session import Session
from tools.executor import (
    ExecutionPlan,
    execute_plan,
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


@dataclass
class Planner:
    """Turn a user utterance into a spoken response via LLM + tools."""

    registry: ToolRegistry = field(default_factory=get_registry)

    def plan_and_execute(
        self,
        user_text: str,
        session: Session,
    ) -> PlannerResult:
        """Run the full cognition pipeline for one user turn."""
        started = time.monotonic()
        session.current_task = user_text
        session.touch()

        try:
            raw = ask_agent(user_text)
        except Exception as exc:
            _logger.exception("LLM pipeline failed")
            return PlannerResult(
                raw_agent_response="",
                payload={},
                spoken_text="Sorry, I had trouble thinking about that.",
                elapsed_sec=time.monotonic() - started,
            )

        _logger.debug("Agent raw response: %s", raw[:200] if raw else "")

        try:
            payload = parse_agent_payload(raw)
        except Exception as exc:
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

        return PlannerResult(
            raw_agent_response=raw,
            payload=payload,
            spoken_text="I didn't understand the response.",
            elapsed_sec=time.monotonic() - started,
        )

    def discover_tools_for_intent(self, intent: str) -> list:
        """Return tools that claim they can handle *intent* (plugin hook)."""
        return self.registry.find_for_intent(intent)
