"""Note domain model."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable, Mapping, Optional

from notes.exceptions import NoteValidationError


def normalise_tags(tags: "str | Iterable[str] | None") -> list[str]:
    """Returns unique, trimmed tags while preserving input order."""
    if tags is None:
        return []
    if isinstance(tags, str):
        raw_tags = tags.split(",")
    else:
        raw_tags = list(tags)

    seen: set[str] = set()
    cleaned: list[str] = []
    for tag in raw_tags:
        value = str(tag).strip().lower()
        if not value or value in seen:
            continue
        seen.add(value)
        cleaned.append(value)
    return cleaned


def tags_to_json(tags: Iterable[str]) -> str:
    return json.dumps(list(tags), ensure_ascii=True)


def tags_from_json(value: str) -> list[str]:
    try:
        decoded = json.loads(value or "[]")
    except json.JSONDecodeError as exc:
        raise NoteValidationError("Stored note tags are not valid JSON.") from exc
    if not isinstance(decoded, list):
        raise NoteValidationError("Stored note tags must be a JSON list.")
    return normalise_tags(decoded)


@dataclass
class Note:
    """A text note with tags and audit timestamps.

    Fields: ``id``, ``title``, ``content``, ``tags``, ``created_at``,
    ``updated_at``.
    """

    title: str
    content: str
    tags: "str | Iterable[str] | None" = None
    id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        if not self.title or not str(self.title).strip():
            raise NoteValidationError("Note.title must be a non-empty string.")
        if self.content is None:
            raise NoteValidationError("Note.content must not be None.")
        self.title = str(self.title).strip()
        self.content = str(self.content)
        self.tags = normalise_tags(self.tags)

    def to_row(self) -> Mapping[str, Any]:
        now = datetime.now()
        return {
            "id": self.id,
            "title": self.title,
            "content": self.content,
            "tags": tags_to_json(self.tags),
            "created_at": (self.created_at or now).isoformat(),
            "updated_at": (self.updated_at or now).isoformat(),
        }

    @classmethod
    def from_row(cls, row: Mapping[str, Any]) -> "Note":
        return cls(
            id=row["id"],
            title=row["title"],
            content=row["content"],
            tags=tags_from_json(row["tags"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )
