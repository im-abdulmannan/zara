"""Document capability — text files and optional DOCX."""
from __future__ import annotations

import os
from typing import Any, ClassVar, Mapping

from tools.base import BaseTool, ToolParameter, ToolResult
from tools.registration import register_tool

_MAX_READ_BYTES = 120_000


def _ensure_parent(path: str) -> None:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)


def _read_docx(path: str) -> tuple[bool, str]:
    try:
        import docx
    except ImportError:
        return False, "DOCX read requires: pip install python-docx"
    try:
        document = docx.Document(path)
        text = "\n".join(paragraph.text for paragraph in document.paragraphs)
        return True, text
    except Exception as exc:
        return False, f"Could not read DOCX: {exc}"


def _write_docx(path: str, content: str) -> tuple[bool, str]:
    from tools.capabilities.docx_format import write_formatted_docx

    return write_formatted_docx(path, content)


@register_tool
class DocumentCapabilityTool(BaseTool):
    name = "document"
    description = (
        "Document capability: read/create/append text or DOCX files, or convert text to DOCX."
    )
    is_capability: ClassVar[bool] = True
    parameters = (
        ToolParameter(
            "operation",
            "One of: read, create, append, to_docx",
        ),
        ToolParameter("path", "File path (.txt, .md, .docx)", required=False),
        ToolParameter("content", "Text content for create/append/to_docx", required=False),
        ToolParameter(
            "destination",
            "Output path for to_docx when different from path",
            required=False,
        ),
    )
    intent_keywords = ("document", "report", "assignment", "write file", "docx", "word")

    def execute(self, params: Mapping[str, Any]) -> ToolResult:
        operation = str(params.get("operation") or "").strip().lower()
        path = os.path.expandvars(
            os.path.expanduser(str(params.get("path") or params.get("destination") or "").strip())
        )
        content = params.get("content")
        text = "" if content is None else str(content)

        if operation == "read":
            return self._read(path)
        if operation == "create":
            return self._create(path, text)
        if operation == "append":
            return self._append(path, text)
        if operation == "to_docx":
            dest = str(params.get("destination") or path or "").strip()
            if not dest:
                return ToolResult(False, "document to_docx requires path or destination.")
            if not dest.lower().endswith(".docx"):
                dest += ".docx"
            ok, message = _write_docx(dest, text)
            return ToolResult(ok, message, {"path": dest})

        return ToolResult(
            False,
            "document requires operation: read, create, append, to_docx.",
        )

    def _read(self, path: str) -> ToolResult:
        if not path:
            return ToolResult(False, "document read requires path.")
        if not os.path.isfile(path):
            return ToolResult(False, f"File not found: {path}")
        ext = os.path.splitext(path)[1].lower()
        if ext == ".docx":
            ok, payload = _read_docx(path)
            if not ok:
                return ToolResult(False, payload)
            preview = payload if len(payload) < 4000 else payload[:3997] + "..."
            return ToolResult(True, preview, {"path": path, "format": "docx"})
        try:
            with open(path, "rb") as handle:
                data = handle.read(_MAX_READ_BYTES + 1)
        except OSError as exc:
            return ToolResult(False, f"Could not read file: {exc}")
        truncated = len(data) > _MAX_READ_BYTES
        if truncated:
            data = data[:_MAX_READ_BYTES]
        try:
            body = data.decode("utf-8")
        except UnicodeDecodeError:
            return ToolResult(False, "Unsupported binary document; use .txt or .docx.")
        preview = body if len(body) < 4000 else body[:3997] + "..."
        return ToolResult(
            True,
            preview,
            {"path": path, "truncated": truncated, "format": ext or "text"},
        )

    def _create(self, path: str, text: str) -> ToolResult:
        if not path:
            return ToolResult(False, "document create requires path.")
        if path.lower().endswith(".docx"):
            ok, message = _write_docx(path, text)
            return ToolResult(ok, message, {"path": path})
        try:
            _ensure_parent(path)
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(text)
            return ToolResult(True, f"Created {path}.", {"path": path})
        except OSError as exc:
            return ToolResult(False, f"Could not create file: {exc}")

    def _append(self, path: str, text: str) -> ToolResult:
        if not path:
            return ToolResult(False, "document append requires path.")
        if path.lower().endswith(".docx"):
            return ToolResult(
                False,
                "Append is not supported for DOCX yet; use create or to_docx.",
            )
        try:
            _ensure_parent(path)
            with open(path, "a", encoding="utf-8") as handle:
                handle.write(text)
            return ToolResult(True, f"Appended to {path}.", {"path": path})
        except OSError as exc:
            return ToolResult(False, f"Could not append file: {exc}")
