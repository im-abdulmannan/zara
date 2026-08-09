"""Tests for filesystem tools (safe, temp-directory operations)."""
from __future__ import annotations

import os
from unittest.mock import patch

from tools.filesystem import parse_count_request, parse_find_request
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
    with patch("tools.filesystem._open_path") as open_mock:
        result = registry.execute(
            "search_files",
            {"query": "report", "directory": str(tmp_path), "open": False},
        )
    assert result.success is True
    assert "report" in result.message.lower()
    open_mock.assert_not_called()


def test_search_files_finds_folders(tmp_path):
    registry = ToolRegistry()
    project = tmp_path / "zara"
    project.mkdir()
    with patch("tools.filesystem._open_path") as open_mock:
        result = registry.execute(
            "search_files",
            {
                "query": "zara",
                "directory": str(tmp_path),
                "kind": "folder",
                "open": True,
            },
        )
    assert result.success is True
    assert str(project) in result.data["folders"]
    assert result.data["opened"] == str(project)
    assert "opening" in result.message.lower()
    open_mock.assert_called_once_with(str(project))


def test_search_files_prefers_exact_folder_name(tmp_path):
    registry = ToolRegistry()
    nested = tmp_path / "other" / "zara-backup"
    nested.mkdir(parents=True)
    exact = tmp_path / "zara"
    exact.mkdir()
    with patch("tools.filesystem._open_path") as open_mock:
        result = registry.execute(
            "search_files",
            {
                "query": "zara",
                "directory": str(tmp_path),
                "kind": "folder",
                "open": True,
            },
        )
    assert result.data["opened"] == str(exact)
    open_mock.assert_called_once_with(str(exact))


def test_parse_find_request_drive_d_folder():
    for utterance, expected_kind in (
        ("find the zara folder from drive d", "folder"),
        ("open the zara folder on D", "folder"),
        ("where is the zara folder on drive D", "folder"),
        ("find zara on D:", "both"),
    ):
        payload = parse_find_request(utterance)
        assert payload is not None, utterance
        assert payload["tool"] == "search_files"
        assert payload["query"].lower() == "zara"
        assert payload["kind"] == expected_kind
        assert payload["open"] is True
        assert payload["directory"].upper().startswith("D:")


def test_count_items_top_level(tmp_path):
    registry = ToolRegistry()
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    (tmp_path / "note.txt").write_text("x", encoding="utf-8")
    result = registry.execute(
        "count_items",
        {"directory": str(tmp_path), "recursive": False},
    )
    assert result.success is True
    assert result.data["top_level_folders"] == 2
    assert result.data["top_level_files"] == 1
    assert "2 folders" in result.message


def test_list_directory_folders(tmp_path):
    registry = ToolRegistry()
    (tmp_path / "alpha").mkdir()
    (tmp_path / "beta").mkdir()
    (tmp_path / "note.txt").write_text("x", encoding="utf-8")
    result = registry.execute(
        "list_directory",
        {"directory": str(tmp_path), "kind": "folder"},
    )
    assert result.success is True
    assert result.data["folder_count"] == 2
    assert "alpha" in result.data["folders"]
    assert result.data["file_count"] == 0


def test_parse_count_request_drive_d():
    payload = parse_count_request("How many files folders do I have in drive D")
    assert payload is not None
    assert payload["tool"] == "count_items"
    assert payload["directory"].upper().startswith("D:")
    assert payload["recursive"] is True
    assert "query" not in payload

    follow = parse_count_request(
        "I would like to view the count",
        recent_text="How many files folders do I have in drive D",
    )
    assert follow is not None
    assert follow["tool"] == "count_items"
    assert follow["directory"].upper().startswith("D:")


def test_parse_count_request_named_folder_ignores_stale_drive():
    for utterance in (
        "How many files folders do I have in zara folder?",
        "How many files folders do I have in zara",
    ):
        payload = parse_count_request(
            utterance,
            recent_text="How many files folders do I have in drive D",
        )
        assert payload is not None, utterance
        assert payload["tool"] == "count_items"
        assert payload["query"].lower() == "zara"
        assert "directory" not in payload or not payload.get("directory")


def test_count_items_by_folder_name(tmp_path):
    registry = ToolRegistry()
    project = tmp_path / "zara"
    project.mkdir()
    (project / "a.txt").write_text("x", encoding="utf-8")
    (project / "sub").mkdir()
    result = registry.execute(
        "count_items",
        {"query": "zara", "directory": str(tmp_path), "recursive": True},
    )
    assert result.success is True
    assert result.data["directory"] == str(project)
    assert result.data["top_level_files"] == 1
    assert result.data["top_level_folders"] == 1


def test_nested_params_are_normalized():
    from tools.executor import execute_plan, normalize_tool_params

    flat = normalize_tool_params(
        {"tool": "search_files", "params": {"query": "zara", "kind": "folder"}}
    )
    assert flat["query"] == "zara"
    assert flat["kind"] == "folder"
    assert "tool" not in flat

    registry = ToolRegistry()
    with patch("tools.filesystem._open_path"):
        plan = execute_plan(
            {
                "tool": "search_files",
                "params": {
                    "query": "__no_such_name_xyz__",
                    "directory": str(os.getcwd()),
                    "open": False,
                },
            },
            registry=registry,
        )
    assert plan.steps
    assert plan.steps[0].success is True
