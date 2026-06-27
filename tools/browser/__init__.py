"""Browser and web tools."""
from __future__ import annotations

from typing import Any, Mapping

from tools.base import BaseTool, ToolParameter, ToolResult
from tools.web import open_website as _open_website, search_google as _search_google


class OpenWebsiteTool(BaseTool):
    name = "open_website"
    description = "Open a website by name or URL in the default browser."
    parameters = (
        ToolParameter("website", "Site name or domain, e.g. youtube, github.com"),
    )

    def execute(self, params: Mapping[str, Any]) -> ToolResult:
        website = (params.get("website") or "").strip()
        if not website:
            return ToolResult(False, "Which website would you like to open?")
        url = _open_website(website)
        return ToolResult(True, f"Opening {website}.", {"url": url})


class LaunchUrlTool(BaseTool):
    name = "launch_url"
    description = "Open a full URL in the default browser."
    parameters = (
        ToolParameter("url", "Full or partial URL to open"),
    )

    def execute(self, params: Mapping[str, Any]) -> ToolResult:
        url = (params.get("url") or params.get("website") or "").strip()
        if not url:
            return ToolResult(False, "Which URL should I open?")
        resolved = _open_website(url)
        return ToolResult(True, f"Opening {resolved}.", {"url": resolved})


class SearchGoogleTool(BaseTool):
    name = "search_google"
    description = "Search Google for a query."
    parameters = (
        ToolParameter("query", "Search query text"),
    )

    def execute(self, params: Mapping[str, Any]) -> ToolResult:
        query = (params.get("query") or "").strip()
        if not query:
            return ToolResult(False, "What would you like to search for?")
        url = _search_google(query)
        return ToolResult(True, f"Searching Google for {query}.", {"url": url})
