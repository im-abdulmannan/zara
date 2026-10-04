"""Multi-query research accumulation and synthesis for document steps."""
from __future__ import annotations

import re
from typing import Any

from agent import llm_complete, llm_complete_json
from core.logging_config import get_logger
from core.task_state import StepObservation, TaskState

_logger = get_logger(__name__)

_SYNTHESIS_SYSTEM = """You are Zara's research synthesizer.

Given a user goal and raw web search snippets, output a concise research brief the writer can use.

Format (plain text, no markdown fences):
1) Key findings (bullet lines with source URLs when present in snippets)
2) Themes / tensions / open questions
3) Suggested outline for a written deliverable (numbered sections)

Be factual; do not invent sources not present in the snippets.
"""

_WRITE_STEP_RE = re.compile(
    r"\b("
    r"write|draft|create|save|produce|compile|prepare|document|assignment|report|essay|deliverable"
    r")\b",
    re.I,
)
_RESEARCH_STEP_RE = re.compile(
    r"\b(research|web_search|search web|gather sources|look up|find sources)\b",
    re.I,
)
_SYNTHESIS_STEP_RE = re.compile(
    r"\b(synthes|summar|analy|organize findings|outline)\b",
    re.I,
)


def is_research_step(task: str) -> bool:
    return bool(_RESEARCH_STEP_RE.search(task or ""))


def is_write_step(task: str) -> bool:
    return bool(_WRITE_STEP_RE.search(task or ""))


def is_synthesis_step(task: str) -> bool:
    return bool(_SYNTHESIS_STEP_RE.search(task or ""))


def has_research_content(state: TaskState) -> bool:
    return bool((state.research_notes or "").strip())


def sufficient_research(state: TaskState, *, min_queries: int = 2) -> bool:
    """True when enough SerpAPI results exist to synthesize and write."""
    if len(state.search_queries_run) < min_queries:
        return False
    return len((state.research_notes or "").strip()) >= 400


def is_web_search_failure(observation: StepObservation) -> bool:
    if observation.success:
        return False
    if any(str(r.get("tool")) == "web_search" for r in observation.tool_results):
        return True
    summary = (observation.summary or "").lower()
    return "web search failed" in summary or "serpapi" in summary


def accumulate_research(state: TaskState, observation: StepObservation) -> None:
    """Append successful web_search output to task research notes."""
    for result in observation.tool_results:
        if str(result.get("tool")) != "web_search" or not result.get("success"):
            continue
        message = str(result.get("message") or "").strip()
        if message:
            state.research_notes = (state.research_notes + "\n\n" + message).strip()
        query = ""
        params = result.get("params")
        if isinstance(params, dict):
            query = str(params.get("query") or "").strip()
        if query and query not in state.search_queries_run:
            state.search_queries_run.append(query)


def research_context_for_llm(state: TaskState, *, max_chars: int = 12_000) -> str:
    notes = (state.research_notes or "").strip()
    if len(notes) > max_chars:
        notes = notes[: max_chars - 3] + "..."
    queries = ", ".join(state.search_queries_run) or "(none logged)"
    return f"Goal: {state.goal}\nQueries run: {queries}\n\nSnippets:\n{notes or '(none)'}"


def synthesize_research(state: TaskState) -> str:
    """LLM synthesis from accumulated SerpAPI snippets."""
    if not has_research_content(state):
        return ""
    raw = llm_complete(
        [
            {"role": "system", "content": _SYNTHESIS_SYSTEM},
            {"role": "user", "content": research_context_for_llm(state)},
        ]
    )
    text = (raw or "").strip()
    if not text:
        return ""
    state.research_synthesis = text
    _logger.info("Research synthesis updated (%d chars)", len(text))
    return text


def ensure_synthesis_before_write(state: TaskState, step_task: str) -> str | None:
    """Auto-synthesize when entering a write step with raw research only."""
    if state.research_synthesis:
        return state.research_synthesis
    if not is_write_step(step_task) and not is_synthesis_step(step_task):
        return None
    if not has_research_content(state):
        return None
    return synthesize_research(state)


def followup_search_queries(state: TaskState, *, max_queries: int = 3) -> list[str]:
    """Suggest additional SerpAPI queries when coverage is thin."""
    if len(state.search_queries_run) >= 3:
        return []
    prompt = (
        "Goal: "
        + state.goal
        + "\nAlready searched: "
        + ", ".join(state.search_queries_run or ["(none)"])
        + "\n\nReturn ONLY JSON:\n"
        '{"queries":["q1","q2"]}\n'
        "Suggest 1-3 focused Google queries not yet run. Empty array if enough."
    )
    raw = llm_complete_json(
        "You suggest follow-up web search queries for research tasks.",
        prompt,
    )
    if not raw:
        return []
    try:
        from tools.executor import parse_agent_payload

        data = parse_agent_payload(raw)
        items = data.get("queries") if isinstance(data, dict) else None
        if not isinstance(items, list):
            return []
        out: list[str] = []
        for item in items[:max_queries]:
            q = str(item).strip()
            if q and q not in state.search_queries_run:
                out.append(q)
        return out
    except Exception:
        return []


def synthesis_prompt_block(state: TaskState) -> str:
    if not state.research_synthesis:
        return ""
    body = state.research_synthesis
    if len(body) > 6000:
        body = body[:5997] + "..."
    return (
        "RESEARCH SYNTHESIS (use as source material for writing; cite URLs from brief):\n"
        + body
        + "\n\nWhen saving to .docx, use plain text (no markdown); document.to_docx applies Word styles."
    )


def record_deliverable_path(state: TaskState, tool_results: list[dict[str, Any]]) -> None:
    """Track files created by document/filesystem tools."""
    from brain.cleanup import record_deliverable_file

    for result in tool_results:
        if not result.get("success"):
            continue
        tool = str(result.get("tool") or "")
        if tool not in {"document", "filesystem", "take_screenshot"}:
            continue
        params = result.get("params") if isinstance(result.get("params"), dict) else {}
        for key in ("path", "destination", "source"):
            value = str(params.get(key) or "").strip()
            if value and value not in state.files_touched:
                state.files_touched.append(value)
    record_deliverable_file(state, tool_results)
