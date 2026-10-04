"""Structured work plans produced by the strategic planner (WHAT + HOW).

Distinct from :class:`tools.executor.ExecutionPlan`, which records concrete
tool calls after the agent chooses capabilities for a single step.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class WorkPlanStatus(str, Enum):
    DRAFT = "draft"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class WorkStep:
    """One high-level step in a user goal (not a tool invocation)."""

    id: int
    task: str
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "task": self.task, "notes": self.notes}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WorkStep:
        return cls(
            id=int(data.get("id", 0)),
            task=str(data.get("task") or "").strip(),
            notes=str(data.get("notes") or "").strip(),
        )


@dataclass
class WorkPlan:
    """Goal and ordered steps before capability-level execution."""

    goal: str
    steps: list[WorkStep] = field(default_factory=list)
    status: WorkPlanStatus = WorkPlanStatus.DRAFT

    def to_dict(self) -> dict[str, Any]:
        return {
            "goal": self.goal,
            "status": self.status.value,
            "steps": [step.to_dict() for step in self.steps],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WorkPlan:
        raw_status = str(data.get("status") or WorkPlanStatus.DRAFT.value)
        try:
            status = WorkPlanStatus(raw_status)
        except ValueError:
            status = WorkPlanStatus.DRAFT
        steps = [
            WorkStep.from_dict(item)
            for item in (data.get("steps") or [])
            if isinstance(item, dict)
        ]
        return cls(
            goal=str(data.get("goal") or "").strip(),
            steps=steps,
            status=status,
        )

    @property
    def step_count(self) -> int:
        return len(self.steps)

    def step_by_id(self, step_id: int) -> WorkStep | None:
        for step in self.steps:
            if step.id == step_id:
                return step
        return None
