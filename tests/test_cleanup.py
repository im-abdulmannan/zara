"""Automatic removal of stray deliverable files after tasks."""
from __future__ import annotations

import os

from brain.cleanup import cleanup_stray_deliverables, norm_path, record_deliverable_file
from core.task_state import TaskState
from tools.registry import ToolRegistry


def test_cleanup_keeps_intended_deletes_stray(tmp_path):
    intended = tmp_path / "ai_assignment.docx"
    stray = tmp_path / "wrong_place.docx"
    intended.write_bytes(b"x")
    stray.write_bytes(b"y")

    state = TaskState(
        goal=f"Save assignment as {intended}",
        intended_deliverable_path=str(intended),
    )
    state.deliverable_files = [norm_path(str(intended)), norm_path(str(stray))]

    registry = ToolRegistry()
    deleted, errors = cleanup_stray_deliverables(state, registry)

    assert errors == []
    assert len(deleted) == 1
    assert norm_path(deleted[0]) == norm_path(str(stray))
    assert intended.is_file()
    assert not stray.exists()


def test_cleanup_skipped_without_intended_path(tmp_path):
    stray = tmp_path / "extra.docx"
    stray.write_bytes(b"x")
    state = TaskState(goal="Write an assignment")
    state.deliverable_files = [norm_path(str(stray))]

    deleted, _ = cleanup_stray_deliverables(state, ToolRegistry())
    assert deleted == []
    assert stray.is_file()


def test_record_deliverable_file_from_tool_message():
    state = TaskState()
    record_deliverable_file(
        state,
        [
            {
                "tool": "document",
                "success": True,
                "message": "Document saved to D:\\out\\report.docx.",
                "params": {"operation": "to_docx", "path": "D:\\out\\report.docx"},
            }
        ],
    )
    assert any("report.docx" in p for p in state.deliverable_files)
