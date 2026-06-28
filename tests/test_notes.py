"""Tests for notes storage."""
from __future__ import annotations


def test_create_note(zara_runtime):
    note = zara_runtime.create_note("Shopping", "Buy eggs and bread")
    assert note.title == "Shopping"
    assert "eggs" in note.content


def test_list_notes(zara_runtime):
    zara_runtime.create_note("Ideas", "Build a robot")
    notes = zara_runtime.list_notes()
    assert any(n.title == "Ideas" for n in notes)


def test_search_notes(zara_runtime):
    zara_runtime.create_note("Recipe", "Pasta with tomato sauce")
    results = zara_runtime.search_notes("pasta")
    assert any("pasta" in n.content.lower() for n in results)
