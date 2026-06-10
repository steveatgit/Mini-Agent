"""Jira reader tool."""

from typing import Any

import httpx

from .base import Tool, ToolResult


class JiraReaderTool(Tool):
    """Read Jira issues by issue key or JQL."""

    def __init__(self, base_url: str, email: str, api_token: str):
        self.base_url = base_url.rstrip("/")
        self.email = email
        self.api_token = api_token

    @property
    def name(self) -> str:
        return "jira_reader"

    @property
    def description(self) -> str:
        return (
            "Read Jira issues by issue key or JQL. "
            "Use this to understand product requirements, bugs, acceptance criteria, and task context."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "issue_key": {
                    "type": "string",
                    "description": "Jira issue key, for example PROJ-123",
                },
                "jql": {
                    "type": "string",
                    "description": "Optional Jira Query Language for searching issues",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of issues to return when using JQL",
                    "default": 10,
                },
            },
        }

    async def execute(
        self,
        issue_key: str | None = None,
        jql: str | None = None,
        max_results: int = 10,
    ) -> ToolResult:
        """Read one issue or search issues."""
        if not self.base_url or not self.email or not self.api_token:
            return ToolResult(success=False, content="", error="Jira credentials are not configured")
        if not issue_key and not jql:
            return ToolResult(success=False, content="", error="Either issue_key or jql is required")

        try:
            async with httpx.AsyncClient(timeout=30, auth=(self.email, self.api_token)) as client:
                if issue_key:
                    response = await client.get(
                        f"{self.base_url}/rest/api/3/issue/{issue_key}",
                        params={"fields": "summary,status,assignee,reporter,description,priority,labels,comment"},
                    )
                    response.raise_for_status()
                    return ToolResult(success=True, content=self._format_issue(response.json()))

                response = await client.get(
                    f"{self.base_url}/rest/api/3/search",
                    params={
                        "jql": jql,
                        "maxResults": max(1, min(max_results, 20)),
                        "fields": "summary,status,assignee,reporter,priority,labels",
                    },
                )
                response.raise_for_status()
                data = response.json()
                issues = data.get("issues", [])
                if not issues:
                    return ToolResult(success=True, content="No Jira issues found.")
                return ToolResult(
                    success=True,
                    content="\n\n".join(self._format_issue(issue, include_description=False) for issue in issues),
                )
        except Exception as e:
            return ToolResult(success=False, content="", error=f"jira_reader failed: {e}")

    def _format_issue(self, issue: dict[str, Any], include_description: bool = True) -> str:
        fields = issue.get("fields", {})
        key = issue.get("key", "")
        summary = fields.get("summary", "")
        status = (fields.get("status") or {}).get("name", "")
        priority = (fields.get("priority") or {}).get("name", "")
        assignee = (fields.get("assignee") or {}).get("displayName", "Unassigned")
        reporter = (fields.get("reporter") or {}).get("displayName", "")
        labels = ", ".join(fields.get("labels") or [])

        parts = [
            f"Key: {key}",
            f"Summary: {summary}",
            f"Status: {status}",
            f"Priority: {priority}",
            f"Assignee: {assignee}",
            f"Reporter: {reporter}",
            f"Labels: {labels}",
        ]

        if include_description:
            description = fields.get("description")
            parts.append(f"Description: {description}")

            comments = ((fields.get("comment") or {}).get("comments") or [])[-5:]
            if comments:
                parts.append("Recent Comments:")
                for comment in comments:
                    author = (comment.get("author") or {}).get("displayName", "")
                    body = comment.get("body", "")
                    parts.append(f"- {author}: {body}")

        return "\n".join(parts)
