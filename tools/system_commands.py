"""Backward-compatible shim — use :func:`tools.system` helpers."""
from __future__ import annotations

from tools.system import get_current_time, lock_pc, restart_pc, shutdown_pc

__all__ = ["get_current_time", "lock_pc", "restart_pc", "shutdown_pc"]
