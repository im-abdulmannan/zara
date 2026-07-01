"""Backward-compatible shim — use :func:`tools.applications.launch_application`."""
from __future__ import annotations

from tools.applications import launch_application


def open_app(app_name: str) -> tuple[bool, str]:
    """Opens a local application on Windows."""
    return launch_application(app_name)
