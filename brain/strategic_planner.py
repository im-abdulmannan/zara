"""LLM-generated work plans (WHAT + HOW) before capability execution."""
from __future__ import annotations

from typing import Any

from agent import llm_complete_json
from core.logging_config import get_logger
from core.work_plan import WorkPlan, WorkStep
from tools.executor import parse_agent_payload

_logger = get_logger(__name__)

_STRATEGIC_MARKERS = (
    "research",
    "assignment",
    "report",
    "analyze",
    "analyse",
    "create a",
    "write a",
    "draft a",
    "prepare a",
    "improve my",
    "revise",
    " and save",
    " then save",
    " step by step",
    "for me",
    "multiple sources",
    "summarize",
    "summarise",
)

_ACTION_VERBS = (
    "find",
    "search",
    "create",
    "write",
    "save",
    "research",
    "open",
    "improve",
    "generate",
    "compile",
)

_PLANNER_SYSTEM = """You are Zara's strategic planner for Windows desktop tasks.

Given a user goal, output ONLY JSON (no markdown fences) in this shape:
{
  "goal": "one-line goal",
  "steps": [
    {"id": 1, "task": "short actionable step"},
    {"id": 2, "task": "..."}
  ]
}

Rules:
- 3 to 10 steps, ordered, each step doable in one agent turn.
- Steps are high-level (research, read files, write document, save) — not raw API names.
- External facts: plan 2–4 "Run web_search for …" steps (SerpAPI via web_search).
- After research, include "Synthesize and organize findings" then "Write deliverable" then
  "Save with document.create or document.to_docx" (include path if user gave one).
- Include save/verify steps when deliverables go to disk (document create/to_docx or filesystem).
- When the user names one output path, save only there; Zara removes other stray deliverables at task end.
- Never plan browser automation, scraping UIs, or live page interaction.
"""


def needs_strategic_plan(user_text: str) -> bool:
    """Heuristic: multi-step goals get a WorkPlan; simple commands stay single-turn."""
    text = (user_text or "").strip()
    if not text:
        return False
    lowered = text.lower()
    words = lowered.split()
    if len(words) >= 14:
        return True
    if any(marker in lowered for marker in _STRATEGIC_MARKERS):
        return True
    if " and " in lowered:
        verbs = sum(1 for verb in _ACTION_VERBS if verb in lowered)
        if verbs >= 2:
            return True
    return False


def _normalize_steps(raw_steps: list[Any], goal: str) -> list[WorkStep]:
    steps: list[WorkStep] = []
    for index, item in enumerate(raw_steps, start=1):
        if isinstance(item, str):
            task = item.strip()
            if task:
                steps.append(WorkStep(id=index, task=task))
            continue
        if not isinstance(item, dict):
            continue
        task = str(item.get("task") or item.get("description") or "").strip()
        if not task:
            continue
        step_id = int(item.get("id") or index)
        steps.append(WorkStep(id=step_id, task=task, notes=str(item.get("notes") or "")))
    if not steps and goal:
        steps = [
            WorkStep(id=1, task="Understand requirements"),
            WorkStep(id=2, task="Execute the goal using available tools"),
            WorkStep(id=3, task="Summarize outcome for the user"),
        ]
    return steps


def parse_work_plan_payload(raw: str, *, fallback_goal: str = "") -> WorkPlan | None:
    """Parse planner LLM output into a :class:`WorkPlan`."""
    try:
        data = parse_agent_payload(raw)
    except Exception:
        _logger.warning("Work plan JSON parse failed")
        return None
    if not isinstance(data, dict):
        return None
    goal = str(data.get("goal") or fallback_goal or "").strip()
    raw_steps = data.get("steps")
    if not isinstance(raw_steps, list):
        return None
    steps = _normalize_steps(raw_steps, goal)
    if not steps:
        return None
    return WorkPlan(goal=goal or fallback_goal, steps=steps)


def generate_work_plan(user_text: str) -> WorkPlan | None:
    """Ask the LLM for a structured work plan."""
    user_prompt = (
        "User goal:\n"
        + user_text.strip()
        + "\n\nReturn the JSON work plan only."
    )
    raw = llm_complete_json(_PLANNER_SYSTEM, user_prompt)
    if not raw:
        return None
    plan = parse_work_plan_payload(raw, fallback_goal=user_text.strip())
    if plan is not None:
        _logger.info("Work plan: %d steps for goal=%r", plan.step_count, plan.goal[:80])
    return plan


def format_work_plan_for_user(plan: WorkPlan) -> str:
    """Human-readable plan outline for the REPL."""
    lines = [f"Plan: {plan.goal}", ""]
    for step in plan.steps:
        lines.append(f"  {step.id}. {step.task}")
    return "\n".join(lines)
