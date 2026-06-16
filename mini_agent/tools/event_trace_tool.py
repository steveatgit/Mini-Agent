"""Tool wrapper for the event trace workflow."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from mini_agent.config import Config
from mini_agent.event_trace_runner import execute_event_trace
from mini_agent.tools.base import Tool, ToolResult


class EventTraceTool(Tool):
    """Run a cited event-trace workflow from the main agent."""

    def __init__(self, workspace_dir: str, config: Config | None = None):
        self.workspace_dir = Path(workspace_dir).expanduser()
        self.config = config

    @property
    def name(self) -> str:
        return "event_trace"

    @property
    def description(self) -> str:
        return (
            "Trace a public event timeline with cited evidence, source validation, "
            "conflict detection, and a Markdown report written inside the workspace. "
            "Use this for incident timelines, evidence chains, source comparison, "
            "or cited chronology reports."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "description": "The event, incident, company, product, or public topic to trace.",
                },
                "sources": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional seed URLs, file:// URLs, or workspace/local source paths.",
                },
                "max_sources": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 20,
                    "default": 8,
                    "description": "Maximum candidate sources to fetch and analyze.",
                },
                "research_depth": {
                    "type": "string",
                    "enum": ["quick", "deep"],
                    "default": "quick",
                    "description": "Use quick for a concise timeline, deep for evidence-heavy research reports.",
                },
                "time_range": {
                    "type": "string",
                    "description": "Optional time range to scope the research, such as '2022-02 to 2024-12'.",
                },
                "focus": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional research focus areas, such as diplomacy, battles, sanctions, or disputes.",
                },
                "use_memory": {
                    "type": "boolean",
                    "default": True,
                    "description": "Whether to use workspace-scoped event evidence memory.",
                },
                "llm_plan": {
                    "type": "boolean",
                    "default": False,
                    "description": "Use the configured LLM to enrich the task plan, with rule fallback.",
                },
                "llm_extract": {
                    "type": "boolean",
                    "default": False,
                    "description": "Use the configured LLM for evidence extraction, with rule fallback.",
                },
                "llm_judge": {
                    "type": "boolean",
                    "default": False,
                    "description": "Use the configured LLM to judge whether quotes support claims, with rule fallback.",
                },
                "llm_reflect": {
                    "type": "boolean",
                    "default": False,
                    "description": "Use the configured LLM to reflect on evidence gaps and trigger targeted follow-up search.",
                },
                "output": {
                    "type": "string",
                    "description": "Optional workspace-relative Markdown report path.",
                },
            },
            "required": ["topic"],
        }

    async def execute(
        self,
        topic: str,
        sources: list[str] | None = None,
        max_sources: int = 8,
        research_depth: str = "quick",
        time_range: str | None = None,
        focus: list[str] | None = None,
        use_memory: bool = True,
        llm_plan: bool = False,
        llm_extract: bool = False,
        llm_judge: bool = False,
        llm_reflect: bool = False,
        output: str | None = None,
    ) -> ToolResult:
        try:
            result, _state = await execute_event_trace(
                topic=topic,
                workspace_dir=self.workspace_dir,
                config=self.config,
                sources=sources,
                max_sources=max_sources,
                research_depth=research_depth,
                time_range=time_range,
                focus=focus,
                use_memory=use_memory,
                llm_plan=llm_plan,
                llm_extract=llm_extract,
                llm_judge=llm_judge,
                llm_reflect=llm_reflect,
                output=output,
            )
        except Exception as exc:
            return ToolResult(success=False, error=str(exc))

        payload = result.to_dict()
        report_target = payload.get("output_path") or payload["report_path"]
        payload["summary"] = (
            f"Generated event trace report with {payload['timeline_count']} timeline item(s): "
            f"{payload['supported_count']} supported, {payload['single_source_count']} single-source, "
            f"{payload['conflicted_count']} conflicted, {payload['unsupported_count']} unsupported. "
            f"Report: {report_target}"
        )
        return ToolResult(success=True, content=json.dumps(payload, ensure_ascii=False, indent=2))
