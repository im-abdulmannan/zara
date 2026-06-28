"""Tests for long-term memory (SQLite)."""
from __future__ import annotations


def test_remember_fact(zara_runtime):
    memory = zara_runtime.remember("fact", "favorite color is blue")
    assert memory.value
    results = zara_runtime.query_memory("color")
    assert len(results) >= 1


def test_remember_name(zara_runtime):
    zara_runtime.remember("name", "Dana")
    results = zara_runtime.query_memory("name")
    assert any("Dana" in m.value for m in results)


def test_query_memory_empty(zara_runtime):
    results = zara_runtime.query_memory("nonexistent_xyz_123")
    assert results == []
