"""Zara UI Package — tray + event bridge (settings UI is React at /)."""
from __future__ import annotations

from ui.bridge import UIEventBridge
from ui.tray import SystemTrayManager

__all__ = [
    "UIEventBridge",
    "SystemTrayManager",
]
