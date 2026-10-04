"""Shared pytest fixtures for isolated Zara tests."""
from __future__ import annotations

import pytest


@pytest.fixture
def tool_registry():
    """Fresh tool registry without global singleton pollution."""
    from tools.registry import ToolRegistry

    return ToolRegistry()
