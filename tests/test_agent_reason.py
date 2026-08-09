"""Tests for the agent think-then-act reasoner."""
from __future__ import annotations

from brain.reason import reason_about_request


def test_reason_count_named_folder():
    decision = reason_about_request(
        "How many files folders do I have in zara",
        recent_text="How many files folders do I have in drive D",
    )
    assert decision.use_llm is False
    assert decision.action is not None
    assert decision.action["tool"] == "count_items"
    assert decision.action["query"] == "zara"
    assert "count" in decision.thought.lower()


def test_reason_open_billboard_without_folder_word():
    decision = reason_about_request("open billboard")
    assert decision.use_llm is False
    assert decision.action is not None
    assert decision.action["tool"] == "search_files"
    assert decision.action["query"] == "billboard"
    assert decision.action["open"] is True


def test_reason_open_known_app():
    decision = reason_about_request("open chrome")
    assert decision.action is not None
    assert decision.action["tool"] == "open_app"
    assert decision.action["name"] == "chrome"


def test_reason_time():
    decision = reason_about_request("what time is it")
    assert decision.action == {"tool": "get_time"}
    assert decision.use_llm is False


def test_reason_existence_question():
    decision = reason_about_request("do I have any zara folder in my system?")
    assert decision.use_llm is False
    assert decision.action is not None
    assert decision.action["tool"] == "search_files"
    assert decision.action["query"] == "zara"
    assert decision.action["kind"] == "folder"
    assert decision.action["open"] is False


def test_reason_existence_quoted_multiword_name():
    decision = reason_about_request(
        'is there any folder "to be deleted" in my system?',
        recent_text='previous search query":"tata"',
    )
    assert decision.use_llm is False
    assert decision.action is not None
    assert decision.action["query"] == "to be deleted"
    assert decision.action["open"] is False


def test_reason_list_folders_on_drive():
    decision = reason_about_request("list all of the folders inside D drive")
    assert decision.use_llm is False
    assert decision.action is not None
    assert decision.action["tool"] == "list_directory"
    assert decision.action["directory"].upper().startswith("D:")
    assert decision.action["kind"] == "folder"


def test_reason_existence_followup_on_drive():
    recent = (
        'User: do I have any zara folder in my system? '
        'Assistant: {"tool":"search_files","query":"zara","kind":"folder","open":false}'
    )
    decision = reason_about_request(
        "Do I have any available in D drive?",
        recent_text=recent,
    )
    assert decision.use_llm is False
    assert decision.action is not None
    assert decision.action["tool"] == "search_files"
    assert decision.action["query"] == "zara"
    assert decision.action["directory"].upper().startswith("D:")
    assert decision.action["open"] is False
