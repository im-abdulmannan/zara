"""Dynamic work-plan updates after step observations."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agent import llm_complete_json
from core.logging_config import get_logger
from brain.research import sufficient_research
from core.task_state import StepObservation, TaskState, TaskStatus
from core.work_plan import WorkPlan, WorkStep
from tools.executor import parse_agent_payload

_logger = get_logger(__name__)

_REPLAN_SYSTEM = """You are Zara's replanning module after a work-plan step finishes.

Output ONLY JSON (no markdown):
{
  "action": "continue",
  "reason": "why"
}

OR when more work is needed before the remaining steps:
{
  "action": "revise",
  "reason": "why",
  "remaining_steps": [
    {"task": "next actionable step"},
    {"task": "..."}
  ]
}

Rules:
- Prefer "continue" when the current plan still fits.
- Use "revise" when web_search results are thin, contradictory, or missing angles.
- If the user already has 3+ successful searches, revise remaining steps to ONLY
  synthesize, write, and save (no more web_search steps).
- remaining_steps replaces all not-yet-completed plan steps (high-level wording).
- 1 to 8 remaining steps max.
"""


@dataclass
class ReplanDecision:
    action: str
    reason: str
    remaining_steps: list[WorkStep]


def should_replan_after(observation: StepObservation, state: TaskState) -> bool:
    """Replan sparingly — avoid resetting the plan after every search."""
    if not observation.success:
        if sufficient_research(state):
            return True
        return True
    if any(
        item.get("tool") == "web_search" and item.get("success")
        for item in observation.tool_results
    ):
        if sufficient_research(state):
            return False
        return len(state.search_queries_run) <= 1
    summary = observation.summary.lower()
    if any(
        phrase in summary
        for phrase in (
            "no web results",
            "needs serpapi",
            "web search failed",
            "not set",
        )
    ):
        return sufficient_research(state) or len(state.search_queries_run) < 2
    return False


def _remaining_plan_steps(state: TaskState) -> list[WorkStep]:
    if state.plan is None:
        return []
    completed = set(state.completed_step_ids)
    if state.current_step_id is not None:
        return [
            step
            for step in state.plan.steps
            if step.id >= state.current_step_id and step.id not in completed
        ]
    return [step for step in state.plan.steps if step.id not in completed]


def parse_replan_payload(raw: str) -> ReplanDecision | None:
    try:
        data = parse_agent_payload(raw)
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    action = str(data.get("action") or "continue").strip().lower()
    reason = str(data.get("reason") or "").strip()
    steps: list[WorkStep] = []
    if action == "revise":
        raw_steps = data.get("remaining_steps")
        if not isinstance(raw_steps, list) or not raw_steps:
            return None
        for index, item in enumerate(raw_steps, start=1):
            if isinstance(item, str):
                task = item.strip()
            elif isinstance(item, dict):
                task = str(item.get("task") or "").strip()
            else:
                continue
            if task:
                steps.append(WorkStep(id=index, task=task))
        if not steps:
            return None
    return ReplanDecision(action=action, reason=reason, remaining_steps=steps)


def apply_replan(state: TaskState, decision: ReplanDecision) -> bool:
    """Merge a revise decision into the active plan. Returns True if plan changed."""
    if decision.action != "revise" or state.plan is None:
        return False

    completed = [s for s in state.plan.steps if s.id in state.completed_step_ids]
    next_id = (max((s.id for s in completed), default=0)) + 1
    new_tail: list[WorkStep] = []
    for item in decision.remaining_steps:
        new_tail.append(WorkStep(id=next_id, task=item.task, notes=item.notes))
        next_id += 1

    state.plan.steps = completed + new_tail
    state.current_step_id = new_tail[0].id if new_tail else None
    if state.current_step_id is None:
        state.status = TaskStatus.COMPLETED
    else:
        state.status = TaskStatus.RUNNING
    _logger.info("Replanned task: %d remaining steps", len(new_tail))
    return True


def maybe_replan(state: TaskState, observation: StepObservation) -> bool:
    """Call LLM to revise plan when observations warrant it."""
    if state.plan is None or not should_replan_after(observation, state):
        return False

    remaining = _remaining_plan_steps(state)
    if not remaining and state.current_step_id is None:
        return False

    obs_lines = [
        f"Step {observation.step_id}: {observation.summary[:500]}",
    ]
    for tr in observation.tool_results[:5]:
        obs_lines.append(
            f"  tool {tr.get('tool')}: success={tr.get('success')} — {str(tr.get('message', ''))[:200]}"
        )

    remaining_lines = "\n".join(f"- {s.task}" for s in remaining) or "(none)"

    user_prompt = (
        f"Goal: {state.goal}\n\n"
        f"Searches completed so far: {len(state.search_queries_run)}\n"
        f"Latest observation:\n" + "\n".join(obs_lines) + "\n\n"
        f"Remaining planned steps:\n{remaining_lines}\n\n"
        "Should we continue or revise remaining steps?"
    )

    state.status = TaskStatus.REPLANNING
    raw = llm_complete_json(_REPLAN_SYSTEM, user_prompt)
    decision = parse_replan_payload(raw) if raw else None
    if decision is None:
        state.status = TaskStatus.RUNNING
        return False

    if decision.action == "revise":
        changed = apply_replan(state, decision)
        if not changed:
            state.status = TaskStatus.RUNNING
        return changed

    state.status = TaskStatus.RUNNING
    return False
