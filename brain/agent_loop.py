"""Execute work-plan steps: act → observe → advance (with optional re-plan)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

from agent import ask_agent_ephemeral, get_last_agent_thought
from brain.replan import maybe_replan
from brain.cleanup import cleanup_stray_deliverables, cleanup_summary
from brain.deliverable import (
    extract_output_path,
    is_save_step,
    try_extract_tool_payload,
    write_deliverable,
)
from brain.research import (
    accumulate_research,
    ensure_synthesis_before_write,
    followup_search_queries,
    is_research_step,
    is_synthesis_step,
    is_web_search_failure,
    is_write_step,
    record_deliverable_path,
    sufficient_research,
    synthesis_prompt_block,
)
from core.guardrails import GuardrailManager
from core.task_store import save_task_state
from core.logging_config import get_logger
from core.session import Session
from core.task_state import StepObservation, TaskState, TaskStatus
from core.work_plan import WorkPlan
from tools.executor import (
    ExecutionPlan,
    execute_plan,
    extract_tool_calls,
    normalize_tool_params,
    parse_agent_payload,
    spoken_response,
)
from tools.registry import ToolRegistry

_logger = get_logger(__name__)

ExecutePayloadFn = Callable[[str, Dict[str, Any], Session], tuple[ExecutionPlan, str]]


@dataclass
class AgentLoopResult:
    spoken_text: str
    used_tools: bool = False
    awaiting_confirmation: bool = False
    task_done: bool = False
    steps_executed: int = 0
    thought: str = ""
    last_payload: Dict[str, Any] | None = None


@dataclass
class AgentLoop:
    registry: ToolRegistry
    guardrails: GuardrailManager
    execute_payload: ExecutePayloadFn
    max_steps_per_turn: int = 12

    def continue_task(self, user_text: str, session: Session) -> AgentLoopResult:
        """Resume a paused/running task (e.g. user said 'continue')."""
        state = session.task_state
        if state is None or state.status not in (
            TaskStatus.RUNNING,
            TaskStatus.REPLANNING,
            TaskStatus.PLANNING,
        ):
            return AgentLoopResult(
                spoken_text="There is no active multi-step task to continue.",
            )
        if user_text.strip().lower() in {"continue", "go on", "next", "proceed"}:
            return self.run_until_done(session)
        state.errors.append(f"User note while task running: {user_text.strip()}")
        return self.run_until_done(session)

    def run_until_done(self, session: Session) -> AgentLoopResult:
        """Execute plan steps until completion, failure, or confirmation gate."""
        state = session.task_state
        if state is None or state.plan is None:
            return AgentLoopResult(spoken_text="No work plan is active.")

        summaries: list[str] = []
        used_tools = False
        last_thought = ""
        steps_run = 0

        while (
            state.status == TaskStatus.RUNNING
            and state.current_step_id is not None
            and steps_run < self.max_steps_per_turn
        ):
            step_result = self._execute_current_step(session)
            last_thought = step_result.thought or last_thought
            steps_run += 1
            used_tools = used_tools or step_result.used_tools

            if step_result.awaiting_confirmation:
                return AgentLoopResult(
                    spoken_text=step_result.spoken_text,
                    used_tools=used_tools,
                    awaiting_confirmation=True,
                    steps_executed=steps_run,
                    thought=last_thought,
                    last_payload=step_result.last_payload,
                )

            summaries.append(step_result.spoken_text)

            if state.status == TaskStatus.FAILED:
                return AgentLoopResult(
                    spoken_text=step_result.spoken_text,
                    used_tools=used_tools,
                    task_done=False,
                    steps_executed=steps_run,
                    thought=last_thought,
                )

            if state.current_step_id is None:
                break

        if state.status == TaskStatus.COMPLETED:
            deleted, cleanup_errors = cleanup_stray_deliverables(state, self.registry)
            if deleted or cleanup_errors:
                _persist_task(session)
            closing = summaries[-1] if summaries else "Task completed."
            body = "\n".join(f"Step done: {line}" for line in summaries if line)
            spoken = f"All steps finished.\n{body}\n{closing}" if len(summaries) > 1 else closing
            extra = cleanup_summary(deleted, cleanup_errors)
            if extra:
                spoken = f"{spoken.strip()}\n{extra}"
            return AgentLoopResult(
                spoken_text=spoken.strip(),
                used_tools=used_tools or bool(deleted),
                task_done=True,
                steps_executed=steps_run,
                thought=last_thought,
            )

        partial = summaries[-1] if summaries else "Paused on this step."
        return AgentLoopResult(
            spoken_text=partial,
            used_tools=used_tools,
            steps_executed=steps_run,
            thought=last_thought,
        )

    def _execute_current_step(self, session: Session) -> AgentLoopResult:
        state = session.task_state
        assert state is not None and state.plan is not None
        step = state.plan.step_by_id(state.current_step_id or 0)
        if step is None:
            state.status = TaskStatus.FAILED
            state.errors.append("Missing current plan step.")
            return AgentLoopResult(spoken_text="I lost track of the plan step.")

        ensure_synthesis_before_write(state, step.task)

        if self._try_auto_deliverable(session, step):
            return self._finish_step_success(
                session,
                step,
                "Saved the deliverable from your research synthesis.",
                thought="Auto-saved deliverable from synthesis.",
            )

        prompt = self._build_step_prompt(state, step.task, step.id)
        raw = ask_agent_ephemeral(prompt, goal=state.goal)
        thought = get_last_agent_thought()

        try:
            payload = parse_agent_payload(raw)
        except Exception:
            payload = try_extract_tool_payload(raw)
            if payload is None and self._try_auto_deliverable(session, step):
                return self._finish_step_success(
                    session,
                    step,
                    "The model response was truncated, but I saved the assignment from synthesis.",
                    thought=thought,
                )
            summary = "Could not parse the model response for this step."
            if raw and len(raw) > 200:
                summary += " (Response was too long or incomplete JSON.)"
            obs = StepObservation(step_id=step.id, summary=summary, success=False)
            state.record_observation(obs)
            state.status = TaskStatus.FAILED
            _persist_task(session)
            return AgentLoopResult(spoken_text=summary, thought=thought)

        if payload.get("thought"):
            thought = str(payload.get("thought"))

        is_chat = payload.get("tool") == "chat" or (
            not payload.get("tool") and not payload.get("tools")
        )
        if is_chat:
            text = str(payload.get("response") or "Step noted.")
            obs = StepObservation(step_id=step.id, summary=text, success=True)
            state.record_observation(obs)
            accumulate_research(state, obs)
            self._post_step_research(state, obs, step.task)
            if not maybe_replan(state, obs):
                state.advance_step()
            _persist_task(session)
            return AgentLoopResult(
                spoken_text=text,
                thought=thought,
                last_payload=payload,
            )

        risky = self._first_risky_call(payload)
        if risky is not None:
            tool_name = str(risky.get("tool", "")).strip()
            prompt_text = self.guardrails.request_confirmation(
                tool_name,
                dict(risky),
                full_payload=payload,
            )
            return AgentLoopResult(
                spoken_text=prompt_text,
                awaiting_confirmation=True,
                thought=thought,
                last_payload=payload,
            )

        exec_plan, spoken = self.execute_payload(raw, payload, session)
        used = bool(exec_plan.steps)
        tool_results = [
            {
                "tool": s.tool,
                "params": dict(s.params),
                "success": s.success,
                "message": s.message,
            }
            for s in exec_plan.steps
        ]
        success = exec_plan.all_succeeded if exec_plan.steps else True
        obs = StepObservation(
            step_id=step.id,
            summary=spoken,
            tool_results=tool_results,
            success=success,
        )
        state.record_observation(obs)
        accumulate_research(state, obs)
        record_deliverable_path(state, tool_results)
        self._post_step_research(state, obs, step.task)

        if not success and is_web_search_failure(obs) and sufficient_research(state):
            state.errors.append(spoken)
            obs = StepObservation(
                step_id=step.id,
                summary=(
                    "Web search timed out or failed, but earlier research is enough. "
                    "Continuing to synthesis and writing."
                ),
                tool_results=tool_results,
                success=True,
            )
            state.observations[-1] = obs
            success = True
            spoken = obs.summary

        if not success:
            state.status = TaskStatus.FAILED
            _persist_task(session)
            return AgentLoopResult(
                spoken_text=spoken,
                used_tools=used,
                thought=thought,
                last_payload=payload,
            )

        if not maybe_replan(state, obs):
            state.advance_step()
        _persist_task(session)
        return AgentLoopResult(
            spoken_text=spoken,
            used_tools=used,
            thought=thought,
            last_payload=payload,
        )

    def _build_step_prompt(self, state: TaskState, step_task: str, step_id: int) -> str:
        total = state.plan.step_count if state.plan else "?"
        prior: list[str] = []
        for obs in state.observations[-6:]:
            prior.append(f"- Step {obs.step_id}: {obs.summary[:400]}")
        prior_block = "\n".join(prior) if prior else "(none yet)"
        synthesis_block = synthesis_prompt_block(state)
        followups = followup_search_queries(state) if is_research_step(step_task) else []
        followup_block = ""
        if followups:
            followup_block = (
                "Suggested follow-up web_search queries (use if gaps remain):\n"
                + "\n".join(f"- {q}" for q in followups)
                + "\n\n"
            )
        return (
            f"WORK PLAN STEP {step_id} of {total}\n"
            f"Step task: {step_task}\n"
            f"Overall goal: {state.goal}\n\n"
            f"Prior observations:\n{prior_block}\n\n"
            + (synthesis_block + "\n\n" if synthesis_block else "")
            + followup_block
            + "Execute only this step. Prefer capabilities: filesystem, document, system, "
            "application, clipboard, web_search. Granular tools still work. "
            "For research steps, call web_search one or more times with focused queries. "
            "For writing/saving: use document.to_docx for .docx paths. Keep JSON small; "
            "research synthesis is already in context above. "
            "Return JSON with thought + tool(s) or chat response."
        )

    def _try_auto_deliverable(self, session: Session, step) -> bool:
        state = session.task_state
        if state is None:
            return False
        if not (is_write_step(step.task) or is_save_step(step.task)):
            return False
        if not extract_output_path(state.goal, step.task):
            return False
        if not (state.research_synthesis or state.research_notes):
            return False
        ok, message, path = write_deliverable(
            state,
            self.registry,
            step_hint=step.task,
        )
        if ok:
            session.record_tool("document", True, message)
            _logger.info("Auto deliverable write: %s", path)
        else:
            _logger.warning("Auto deliverable write failed: %s", message)
        return ok

    def _finish_step_success(
        self,
        session: Session,
        step,
        spoken: str,
        *,
        thought: str = "",
    ) -> AgentLoopResult:
        state = session.task_state
        assert state is not None
        obs = StepObservation(step_id=step.id, summary=spoken, success=True)
        state.record_observation(obs)
        record_deliverable_path(
            state,
            [{"tool": "document", "success": True, "message": spoken}],
        )
        if not maybe_replan(state, obs):
            state.advance_step()
        _persist_task(session)
        return AgentLoopResult(
            spoken_text=spoken,
            used_tools=True,
            thought=thought,
        )

    def _post_step_research(
        self,
        state: TaskState,
        observation: StepObservation,
        step_task: str,
    ) -> None:
        if is_synthesis_step(step_task) and observation.success:
            from brain.research import synthesize_research

            synthesize_research(state)
        elif (
            is_research_step(step_task)
            and observation.success
            and len(state.search_queries_run) < 2
        ):
            _logger.debug("Research step with <2 queries; replan may add more")

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


def start_task(session: Session, plan: WorkPlan, *, user_text: str = "") -> TaskState:
    """Attach a new task to the session."""
    state = TaskState(goal=plan.goal)
    path = extract_output_path(user_text, plan.goal)
    if path:
        state.intended_deliverable_path = path
    state.start_plan(plan)
    session.task_state = state
    session.current_task = plan.goal
    _persist_task(session)
    return state


def _persist_task(session: Session) -> None:
    save_task_state(session.conversation_id, session.task_state)
