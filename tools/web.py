"""Backward-compatible shim — use :func:`tools.browser.resolve_website`."""
from __future__ import annotations

from tools.browser import resolve_website, search_google

__all__ = ["open_website", "search_google"]


def open_website(site_name: str) -> str:
    """Opens a website by name or direct URL."""
    return resolve_website(site_name)
