"""Browser and web tools."""
from __future__ import annotations

import urllib.parse
from typing import Any, Mapping

from tools.base import BaseTool, ToolParameter, ToolResult
from tools.registration import register_tool
from tools.url_opener import open_url

WEBSITES: dict[str, str] = {
    "google": "google.com",
    "youtube": "youtube.com",
    "github": "github.com",
    "gmail": "mail.google.com",
    "facebook": "facebook.com",
    "twitter": "twitter.com",
    "reddit": "reddit.com",
    "stackoverflow": "stackoverflow.com",
    "wikipedia": "wikipedia.org",
}


def resolve_website(site_name: str) -> str:
    """Resolve a site name or URL and open it in the default browser."""
    normalized = site_name.lower().strip()
    if normalized in WEBSITES:
        url = WEBSITES[normalized]
    elif "." in normalized:
        url = normalized
    else:
        url = f"{normalized}.com"
    open_url(url)
    return url


def search_google(query: str) -> str:
    """Search Google for *query* and return the URL opened."""
    encoded_query = urllib.parse.quote(query.strip())
    url = f"https://www.google.com/search?q={encoded_query}"
    open_url(url)
    return url


@register_tool
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
        url = resolve_website(website)
        return ToolResult(True, f"Opening {website}.", {"url": url})


@register_tool
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
        resolved = resolve_website(url)
        return ToolResult(True, f"Opening {resolved}.", {"url": resolved})


@register_tool
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
        url = search_google(query)
        return ToolResult(True, f"Searching Google for {query}.", {"url": url})
