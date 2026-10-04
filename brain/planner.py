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
from brain.agent_loop import AgentLoop, start_task
from brain.strategic_planner import (
    format_work_plan_for_user,
    generate_work_plan,
    needs_strategic_plan,
)
from core.guardrails import GuardrailManager
from core.logging_config import get_logger
from core.session import Session
from core.task_state import StepObservation, TaskStatus
from core.task_store import save_task_state
from core.work_plan import WorkPlan
from tools.executor import (
    ExecutionPlan,
    execute_plan,
    extract_tool_calls,
    normalize_tool_params,
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
    work_plan: Optional[WorkPlan] = None
    work_plan_outline: str = ""
    spoken_text: str = ""
    used_tools: bool = False
    elapsed_sec: float = 0.0
    awaiting_confirmation: bool = False
    thought: str = ""
    task_done: bool = False


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
            pending = self._resolve_pending_confirmation(user_text, session, started)
            if pending.awaiting_confirmation:
                return pending
            if session.task_state and session.task_state.status == TaskStatus.RUNNING:
                loop_result = self._agent_loop().run_until_done(session)
                return self._from_loop_result(loop_result, session, started)
            return pending

        if session.task_state and session.task_state.status in (
            TaskStatus.RUNNING,
            TaskStatus.REPLANNING,
        ):
            loop_result = self._agent_loop().continue_task(user_text, session)
            return self._from_loop_result(loop_result, session, started)

        if session.task_state and session.task_state.status == TaskStatus.COMPLETED:
            save_task_state(session.conversation_id, None)
            session.task_state = None

        if needs_strategic_plan(user_text):
            strategic = self._run_strategic_plan(user_text, session, started)
            if strategic is not None:
                return strategic

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

        from agent import get_last_agent_thought

        thought = get_last_agent_thought()
        _logger.debug("Agent raw response: %s", raw[:200] if raw else "")

        try:
            payload = parse_agent_payload(raw)
        except Exception:
            cleaned = (raw or "").strip()
            if not cleaned:
                _logger.warning("Agent returned empty response")
                return PlannerResult(
                    raw_agent_response=raw,
                    payload={},
                    spoken_text=(
                        "The model returned an empty reply. "
                        "Try again, or set a different MODEL_NAME in your .env file."
                    ),
                    thought=thought,
                    elapsed_sec=time.monotonic() - started,
                )
            # Free / weaker models often return prose instead of JSON — speak it.
            _logger.warning(
                "Failed to parse agent JSON; treating as chat. Preview=%r",
                cleaned[:160],
            )
            return PlannerResult(
                raw_agent_response=raw,
                payload={"tool": "chat", "response": cleaned},
                spoken_text=cleaned,
                thought=thought,
                elapsed_sec=time.monotonic() - started,
            )

        if isinstance(payload, dict) and payload.get("thought"):
            thought = str(payload.get("thought") or thought)

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
                thought=thought,
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
                    thought=thought,
                    elapsed_sec=time.monotonic() - started,
                )

            result = self._execute_payload(raw, payload, session, started)
            result.thought = thought
            return result

        return PlannerResult(
            raw_agent_response=raw,
            payload=payload,
            spoken_text="I didn't understand the response.",
            thought=thought,
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
        if session.task_state and session.task_state.status == TaskStatus.RUNNING:
            exec_plan, spoken = self._execute_payload_for_loop("", payload, session)
            state = session.task_state
            step_id = state.current_step_id or 0
            tool_results = [
                {"tool": s.tool, "success": s.success, "message": s.message}
                for s in exec_plan.steps
            ]
            success = exec_plan.all_succeeded if exec_plan.steps else True
            state.record_observation(
                StepObservation(
                    step_id=step_id,
                    summary=spoken or reply,
                    tool_results=tool_results,
                    success=success,
                )
            )
            if success:
                state.advance_step()
            else:
                state.status = TaskStatus.FAILED
            loop_result = self._agent_loop().run_until_done(session)
            merged = self._from_loop_result(loop_result, session, started)
            if not merged.spoken_text:
                merged.spoken_text = spoken or reply
            return merged

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
            args = normalize_tool_params(call)
            if self.guardrails.needs_confirmation(
                tool_name,
                requires_confirmation=requires,
                arguments=args,
            ):
                return call
        return None

    def _agent_loop(self) -> AgentLoop:
        return AgentLoop(
            registry=self.registry,
            guardrails=self.guardrails,
            execute_payload=self._execute_payload_for_loop,
        )

    def _execute_payload_for_loop(
        self,
        raw: str,
        payload: Dict[str, Any],
        session: Session,
    ) -> tuple[ExecutionPlan, str]:
        plan = execute_plan(payload, registry=self.registry)
        for step in plan.steps:
            session.record_tool(step.tool, step.success, step.message)
        return plan, spoken_response(plan, payload)

    def _run_strategic_plan(
        self,
        user_text: str,
        session: Session,
        started: float,
    ) -> PlannerResult | None:
        work = generate_work_plan(user_text)
        if work is None:
            _logger.warning("Strategic plan generation failed; using single-turn path")
            return None

        start_task(session, work, user_text=user_text)
        outline = format_work_plan_for_user(work)
        loop_result = self._agent_loop().run_until_done(session)

        if loop_result.task_done:
            save_task_state(session.conversation_id, None)
            if session.task_state:
                session.task_state.status = TaskStatus.COMPLETED

        return PlannerResult(
            raw_agent_response="",
            payload=loop_result.last_payload or {},
            work_plan=work,
            work_plan_outline=outline,
            spoken_text=loop_result.spoken_text,
            used_tools=loop_result.used_tools,
            awaiting_confirmation=loop_result.awaiting_confirmation,
            thought=loop_result.thought,
            task_done=loop_result.task_done,
            elapsed_sec=time.monotonic() - started,
        )

    def _from_loop_result(
        self,
        loop_result,
        session: Session,
        started: float,
    ) -> PlannerResult:
        if loop_result.task_done:
            save_task_state(session.conversation_id, None)
            if session.task_state:
                session.task_state.status = TaskStatus.COMPLETED
        work = session.task_state.plan if session.task_state else None
        return PlannerResult(
            raw_agent_response="",
            payload=loop_result.last_payload or {},
            work_plan=work,
            spoken_text=loop_result.spoken_text,
            used_tools=loop_result.used_tools,
            awaiting_confirmation=loop_result.awaiting_confirmation,
            thought=loop_result.thought,
            task_done=loop_result.task_done,
            elapsed_sec=time.monotonic() - started,
        )
