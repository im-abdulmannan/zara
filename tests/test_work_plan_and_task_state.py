"""Tests for strategic work plans and multi-step task state."""
from __future__ import annotations

from core.work_plan import WorkPlan, WorkPlanStatus, WorkStep
from core.task_state import StepObservation, TaskState, TaskStatus


def test_work_plan_round_trip():
    plan = WorkPlan(
        goal="Create assignment",
        steps=[
            WorkStep(id=1, task="Research topic"),
            WorkStep(id=2, task="Write document"),
        ],
        status=WorkPlanStatus.DRAFT,
    )
    restored = WorkPlan.from_dict(plan.to_dict())
    assert restored.goal == plan.goal
    assert restored.step_count == 2
    assert restored.step_by_id(2).task == "Write document"


def test_task_state_start_and_advance():
    plan = WorkPlan(
        goal="Resume update",
        steps=[
            WorkStep(id=1, task="Find resume"),
            WorkStep(id=2, task="Revise content"),
            WorkStep(id=3, task="Save to Jobs folder"),
        ],
    )
    state = TaskState()
    state.start_plan(plan)

    assert state.status == TaskStatus.RUNNING
    assert state.current_step_id == 1
    assert state.next_step_task == "Find resume"

    state.record_observation(
        StepObservation(step_id=1, summary="Found resume at D:\\resume.docx")
    )
    next_step = state.advance_step()
    assert next_step is not None
    assert next_step.id == 2
    assert state.current_step_id == 2

    state.record_observation(StepObservation(step_id=2, summary="Revised"))
    state.advance_step()
    state.record_observation(StepObservation(step_id=3, summary="Saved"))
    state.advance_step()

    assert state.status == TaskStatus.COMPLETED
    assert state.current_step_id is None
    assert state.completed_step_ids == [1, 2, 3]


def test_task_state_serialization():
    state = TaskState(goal="Test", status=TaskStatus.RUNNING)
    state.errors.append("minor glitch")
    round_trip = TaskState.from_dict(state.to_dict())
    assert round_trip.goal == "Test"
    assert round_trip.status == TaskStatus.RUNNING
    assert round_trip.errors == ["minor glitch"]
