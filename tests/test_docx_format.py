"""DOCX writer applies Word styles instead of raw markdown lines."""
from __future__ import annotations

import pytest

docx = pytest.importorskip("docx")

from tools.capabilities.docx_format import populate_document, write_formatted_docx


def test_markdown_headings_become_word_headings(tmp_path):
    path = tmp_path / "out.docx"
    content = (
        "**Executive Summary**\n\n"
        "Body paragraph one.\n\n"
        "## Section Two\n\n"
        "- First bullet\n"
        "- Second bullet\n"
    )
    ok, _ = write_formatted_docx(str(path), content)
    assert ok
    document = docx.Document(str(path))
    styles = [p.style.name for p in document.paragraphs if p.text.strip()]
    assert "Heading 2" in styles
    assert any("Body paragraph" in p.text for p in document.paragraphs)
    assert not any(p.text.startswith("**") for p in document.paragraphs)


def test_plain_assignment_structure(tmp_path):
    path = tmp_path / "assignment.docx"
    content = (
        "AI Impact on Software Engineering in 2026\n\n"
        "Introduction\n\n"
        "Opening paragraph.\n\n"
        "Emerging Practices\n\n"
        "Details here.\n\n"
        "Conclusion\n\n"
        "Final thoughts.\n"
    )
    ok, _ = write_formatted_docx(str(path), content)
    assert ok
    document = docx.Document(str(path))
    texts = [p.text for p in document.paragraphs]
    assert "Introduction" in texts
    assert any("Opening paragraph" in t for t in texts)
