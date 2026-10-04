"""Mutable state for a multi-step user task (beyond conversation history)."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from core.work_plan import WorkPlan, WorkPlanStatus, WorkStep


class TaskStatus(str, Enum):
    IDLE = "idle"
    PLANNING = "planning"
    RUNNING = "running"
    REPLANNING = "replanning"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class StepObservation:
    """Result of executing one work-plan step (tools + LLM notes)."""

    step_id: int
    summary: str
    tool_results: list[dict[str, Any]] = field(default_factory=list)
    success: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "summary": self.summary,
            "tool_results": list(self.tool_results),
            "success": self.success,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StepObservation:
        return cls(
            step_id=int(data.get("step_id", 0)),
            summary=str(data.get("summary") or ""),
            tool_results=[
                dict(item)
                for item in (data.get("tool_results") or [])
                if isinstance(item, dict)
            ],
            success=bool(data.get("success", True)),
        )


@dataclass
class TaskState:
    """Execution context for a goal that may span many agent loop iterations."""

    goal: str = ""
    status: TaskStatus = TaskStatus.IDLE
    plan: WorkPlan | None = None
    current_step_id: int | None = None
    completed_step_ids: list[int] = field(default_factory=list)
    observations: list[StepObservation] = field(default_factory=list)
    files_touched: list[str] = field(default_factory=list)
    deliverable_files: list[str] = field(default_factory=list)
    intended_deliverable_path: str = ""
    research_notes: str = ""
    research_synthesis: str = ""
    search_queries_run: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "goal": self.goal,
            "status": self.status.value,
            "plan": self.plan.to_dict() if self.plan else None,
            "current_step_id": self.current_step_id,
            "completed_step_ids": list(self.completed_step_ids),
            "observations": [obs.to_dict() for obs in self.observations],
            "files_touched": list(self.files_touched),
            "deliverable_files": list(self.deliverable_files),
            "intended_deliverable_path": self.intended_deliverable_path,
            "research_notes": self.research_notes,
            "research_synthesis": self.research_synthesis,
            "search_queries_run": list(self.search_queries_run),
            "errors": list(self.errors),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TaskState:
        raw_status = str(data.get("status") or TaskStatus.IDLE.value)
        try:
            status = TaskStatus(raw_status)
        except ValueError:
            status = TaskStatus.IDLE
        plan_data = data.get("plan")
        plan = WorkPlan.from_dict(plan_data) if isinstance(plan_data, dict) else None
        return cls(
            goal=str(data.get("goal") or ""),
            status=status,
            plan=plan,
            current_step_id=data.get("current_step_id"),
            completed_step_ids=[
                int(x) for x in (data.get("completed_step_ids") or []) if x is not None
            ],
            observations=[
                StepObservation.from_dict(item)
                for item in (data.get("observations") or [])
                if isinstance(item, dict)
            ],
            files_touched=[str(p) for p in (data.get("files_touched") or [])],
            deliverable_files=[str(p) for p in (data.get("deliverable_files") or [])],
            intended_deliverable_path=str(data.get("intended_deliverable_path") or ""),
            research_notes=str(data.get("research_notes") or ""),
            research_synthesis=str(data.get("research_synthesis") or ""),
            search_queries_run=[
                str(q) for q in (data.get("search_queries_run") or []) if q
            ],
            errors=[str(e) for e in (data.get("errors") or [])],
        )

    def start_plan(self, plan: WorkPlan) -> None:
        self.goal = plan.goal or self.goal
        self.plan = plan
        plan.status = WorkPlanStatus.RUNNING
        self.status = TaskStatus.RUNNING
        if plan.steps:
            self.current_step_id = plan.steps[0].id
        else:
            self.current_step_id = None

    def record_observation(self, observation: StepObservation) -> None:
        self.observations.append(observation)
        if observation.success and observation.step_id not in self.completed_step_ids:
            self.completed_step_ids.append(observation.step_id)
        if not observation.success:
            self.errors.append(observation.summary)

    def advance_step(self) -> WorkStep | None:
        """Move to the next plan step after *current_step_id* completes."""
        if self.plan is None or self.current_step_id is None:
            return None
        ids = [s.id for s in self.plan.steps]
        try:
            index = ids.index(self.current_step_id)
        except ValueError:
            return None
        if index + 1 >= len(self.plan.steps):
            self.current_step_id = None
            self.status = TaskStatus.COMPLETED
            self.plan.status = WorkPlanStatus.COMPLETED
            return None
        next_step = self.plan.steps[index + 1]
        self.current_step_id = next_step.id
        return next_step

    @property
    def next_step_task(self) -> str | None:
        if self.plan is None or self.current_step_id is None:
            return None
        step = self.plan.step_by_id(self.current_step_id)
        return step.task if step else None
