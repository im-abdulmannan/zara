"""Web search via SerpAPI (web_search capability)."""
from __future__ import annotations

import json
import os
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Mapping

from tools.base import BaseTool, ToolParameter, ToolResult
from tools.registration import register_tool

_SERPAPI_URL = "https://serpapi.com/search.json"


def _api_key() -> str:
    return (os.getenv("SERPAPI_API_KEY") or os.getenv("SERP_API_KEY") or "").strip()


def web_search(query: str, *, num: int = 8) -> tuple[bool, str, dict[str, Any]]:
    """Google search through SerpAPI (https://serpapi.com/)."""
    api_key = _api_key()
    if not api_key:
        return (
            False,
            "Web search needs SERPAPI_API_KEY in .env (get one at serpapi.com).",
            {},
        )

    params = urllib.parse.urlencode(
        {
            "engine": "google",
            "q": query.strip(),
            "api_key": api_key,
            "num": max(1, min(num, 10)),
        }
    )
    url = f"{_SERPAPI_URL}?{params}"
    ssl_context: ssl.SSLContext | None = None
    try:
        import certifi

        ssl_context = ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        ssl_context = None

    timeout_sec = int(os.getenv("SERPAPI_TIMEOUT_SEC") or "45")
    max_attempts = max(1, int(os.getenv("SERPAPI_RETRY_ATTEMPTS") or "2"))
    last_error: Exception | None = None
    payload: dict[str, Any] | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            with urllib.request.urlopen(
                url, timeout=timeout_sec, context=ssl_context
            ) as response:
                payload = json.loads(response.read().decode("utf-8"))
            break
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:200]
            return False, f"SerpAPI HTTP {exc.code}: {detail}", {}
        except Exception as exc:
            last_error = exc
            if attempt < max_attempts:
                time.sleep(1.5 * attempt)
                continue
            return False, f"Web search failed: {exc}", {}

    if payload is None:
        return False, f"Web search failed: {last_error or 'unknown error'}", {}

    organic = payload.get("organic_results") or []
    if not organic:
        return True, f"No web results for {query!r}.", {"query": query, "results": []}

    lines = [f"Web results for {query!r}:"]
    results: list[dict[str, str]] = []
    for index, item in enumerate(organic[:num], start=1):
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "Untitled")
        link = str(item.get("link") or "")
        snippet = str(item.get("snippet") or "").replace("\n", " ")
        lines.append(f"{index}. {title} — {snippet[:220]}")
        if link:
            lines.append(f"   {link}")
        results.append({"title": title, "link": link, "snippet": snippet})
    return True, "\n".join(lines), {"query": query, "results": results}


@register_tool
class WebSearchTool(BaseTool):
    name = "web_search"
    description = "Search the web via SerpAPI for current information and research."
    parameters = (
        ToolParameter("query", "Search query", required=True),
        ToolParameter(
            "num",
            "Number of results (1-10)",
            required=False,
            type="integer",
        ),
    )
    intent_keywords = ("search the web", "google", "research online", "look up")

    def execute(self, params: Mapping[str, Any]) -> ToolResult:
        query = str(params.get("query") or "").strip()
        if not query:
            return ToolResult(False, "web_search requires a query.")
        try:
            num = int(params.get("num") or 8)
        except (TypeError, ValueError):
            num = 8
        ok, message, data = web_search(query, num=num)
        return ToolResult(ok, message, data)
