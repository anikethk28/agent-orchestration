"""Web search tool using DuckDuckGo (no API key needed)."""
from __future__ import annotations

from duckduckgo_search import DDGS

from .registry import ToolDefinition, get_registry


def web_search(query: str, max_results: int = 5) -> list[dict]:
    """Search the web and return structured results."""
    results = []
    with DDGS() as ddgs:
        for r in ddgs.text(query, max_results=max_results):
            results.append({"title": r.get("title", ""), "url": r.get("href", ""), "snippet": r.get("body", "")})
    return results


def register_web_search(registry=None) -> None:
    if registry is None:
        registry = get_registry()
    registry.register(
        ToolDefinition(
            name="web_search",
            description="Search the internet for information on a topic. Returns titles, URLs, and snippets.",
            fn=web_search,
            allowed_specialists=["researcher", "analyst", "writer"],
            input_schema={"query": "str", "max_results": "int (default 5)"},
            output_schema={"results": "list of {title, url, snippet}"},
            rate_limit_rpm=10,
        )
    )
