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
