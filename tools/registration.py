"""Tool registration decorator used by auto-discovery."""
from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar

if TYPE_CHECKING:
    from tools.base import BaseTool

T = TypeVar("T", bound="BaseTool")

_REGISTERED_TOOL_CLASSES: list[type[BaseTool]] = []


def register_tool(cls: type[T]) -> type[T]:
    """Register a :class:`BaseTool` subclass for auto-discovery."""
    _REGISTERED_TOOL_CLASSES.append(cls)
    return cls


def registered_tool_classes() -> list[type[BaseTool]]:
    """Return all tool classes registered via :func:`register_tool`."""
    return list(_REGISTERED_TOOL_CLASSES)


def clear_registered_tools() -> None:
    """Clear registrations (for tests)."""
    _REGISTERED_TOOL_CLASSES.clear()
