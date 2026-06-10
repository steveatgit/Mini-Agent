"""Web search tool."""

from typing import Any

import httpx

from .base import Tool, ToolResult


class WebSearchTool(Tool):
    """Search the web through a configurable search API."""

    def __init__(self, api_key: str | None = None, endpoint: str | None = None):
        self.api_key = api_key or ""
        self.endpoint = endpoint or "https://api.tavily.com/search"

    @property
    def name(self) -> str:
        return "web_search"

    @property
    def description(self) -> str:
        return (
            "Search the web for up-to-date external information. "
            "Use this when the answer depends on current facts, external documentation, news, prices, or recent changes."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query",
                },
                "num_results": {
                    "type": "integer",
                    "description": "Maximum number of search results to return",
                    "default": 5,
                },
            },
            "required": ["query"],
        }

    async def execute(self, query: str, num_results: int = 5) -> ToolResult:
        """Execute a web search request."""
        if not self.api_key:
            return ToolResult(
                success=False,
                content="",
                error="web_search API key is not configured",
            )

        try:
            payload = {
                "api_key": self.api_key,
                "query": query,
                "max_results": max(1, min(num_results, 10)),
            }
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.post(self.endpoint, json=payload)
                response.raise_for_status()
                data = response.json()

            results = data.get("results", [])
            if not results:
                return ToolResult(success=True, content="No search results found.")

            lines = []
            for idx, item in enumerate(results, 1):
                title = item.get("title", "")
                url = item.get("url", "")
                snippet = item.get("content", "") or item.get("snippet", "")
                lines.append(f"{idx}. Title: {title}\n   URL: {url}\n   Snippet: {snippet}")

            return ToolResult(success=True, content="\n\n".join(lines))
        except Exception as e:
            return ToolResult(success=False, content="", error=f"web_search failed: {e}")
