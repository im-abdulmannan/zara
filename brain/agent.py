"""Thin wrapper around the legacy agent for backward compatibility."""
from __future__ import annotations

from agent import ask_agent, build_system_prompt

__all__ = ["ask_agent", "build_system_prompt"]
