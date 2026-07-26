"""Tests for filesystem tools (safe, temp-directory operations)."""
from __future__ import annotations

import os

from tools.registry import ToolRegistry


def test_create_folder_tool(tmp_path):
    registry = ToolRegistry()
    target = tmp_path / "new_folder"
    result = registry.execute("create_folder", {"path": str(target)})
    assert result.success is True
    assert target.is_dir()


def test_copy_and_delete_file(tmp_path):
    registry = ToolRegistry()
    source = tmp_path / "source.txt"
    source.write_text("hello", encoding="utf-8")
    dest = tmp_path / "dest.txt"

    copy_result = registry.execute(
        "copy_file",
        {"source": str(source), "destination": str(dest)},
    )
    assert copy_result.success is True
    assert dest.exists()

    delete_result = registry.execute("delete_file", {"path": str(dest)})
    assert delete_result.success is True
    assert not dest.exists()


def test_search_files_tool(tmp_path):
    registry = ToolRegistry()
    (tmp_path / "report.pdf").write_text("x", encoding="utf-8")
    result = registry.execute(
        "search_files",
        {"query": "report", "directory": str(tmp_path)},
    )
    assert result.success is True
    assert "report" in result.message.lower()


def test_search_files_finds_folders(tmp_path):
    registry = ToolRegistry()
    project = tmp_path / "zara"
    project.mkdir()
    result = registry.execute(
        "search_files",
        {"query": "zara", "directory": str(tmp_path), "kind": "folder"},
    )
    assert result.success is True
    assert str(project) in result.data["folders"]


def test_nested_params_are_normalized():
    from tools.executor import execute_plan, normalize_tool_params

    flat = normalize_tool_params(
        {"tool": "search_files", "params": {"query": "zara", "kind": "folder"}}
    )
    assert flat["query"] == "zara"
    assert flat["kind"] == "folder"
    assert "tool" not in flat

    registry = ToolRegistry()
    plan = execute_plan(
        {"tool": "search_files", "params": {"query": "__no_such_name_xyz__", "directory": str(os.getcwd())}},
        registry=registry,
    )
    assert plan.steps
    assert plan.steps[0].success is True
