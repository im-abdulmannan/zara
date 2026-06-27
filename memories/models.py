"""Memory domain model."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping, Optional

from memories.exceptions import MemoryValidationError


@dataclass
class Memory:
    """A single durable fact.

    Fields: ``id``, ``category``, ``key``, ``value``, ``created_at``,
    ``updated_at``.
    """

    key: str
    value: str
    category: str = "general"
    id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        if not self.key or not str(self.key).strip():
            raise MemoryValidationError("Memory.key must be a non-empty string.")
        if self.value is None:
            raise MemoryValidationError("Memory.value must not be None.")
        self.key = str(self.key).strip()
        self.category = (self.category or "general").strip() or "general"

    def to_row(self) -> Mapping[str, Any]:
        now = datetime.now()
        return {
            "id": self.id,
            "category": self.category,
            "key": self.key,
            "value": self.value,
            "created_at": (self.created_at or now).isoformat(),
            "updated_at": (self.updated_at or now).isoformat(),
        }

    @classmethod
    def from_row(cls, row: Mapping[str, Any]) -> "Memory":
        return cls(
            id=row["id"],
            category=row["category"],
            key=row["key"],
            value=row["value"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )
