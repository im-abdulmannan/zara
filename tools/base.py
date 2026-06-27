"""Core abstractions for Zara tools."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class ToolParameter:
    """Schema for a single tool argument."""

    name: str
    description: str
    required: bool = True
    type: str = "string"


@dataclass(frozen=True)
class ToolResult:
    """Structured outcome from tool execution."""

    success: bool
    message: str
    data: dict[str, Any] = field(default_factory=dict)

    def as_tuple(self) -> tuple[bool, str]:
        """Backward-compatible ``(success, message)`` shape."""
        return self.success, self.message


class BaseTool(ABC):
    """Executable capability exposed to the LLM and intent router."""

    name: str
    description: str
    parameters: tuple[ToolParameter, ...] = ()

    @abstractmethod
    def execute(self, params: Mapping[str, Any]) -> ToolResult:
        """Run the tool with validated parameters."""

    def schema(self) -> dict[str, Any]:
        """Return a JSON-schema-like description for prompt generation."""
        props: dict[str, Any] = {}
        required: list[str] = []
        for param in self.parameters:
            props[param.name] = {
                "type": param.type,
                "description": param.description,
            }
            if param.required:
                required.append(param.name)
        return {
            "name": self.name,
            "description": self.description,
            "parameters": props,
            "required": required,
        }

    def prompt_example(self) -> str:
        """Return a short JSON example for the system prompt."""
        example: dict[str, Any] = {"tool": self.name}
        for param in self.parameters:
            if param.required:
                example[param.name] = f"<{param.name}>"
        return str(example).replace("'", '"')
