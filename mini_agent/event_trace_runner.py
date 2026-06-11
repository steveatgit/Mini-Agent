"""Shared event trace execution helpers for CLI and tools."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from mini_agent.config import Config
from mini_agent.event_trace import (
    CitationJudge,
    DefaultPageFetcher,
    EventTraceAgent,
    EventTraceMemory,
    EventTraceRunRecorder,
    LLMEvidenceExtractor,
    ResponsibleTaskPlanner,
    Source,
    TavilySearchProvider,
    state_to_jsonable,
)
from mini_agent.llm import LLMClient
from mini_agent.schema import LLMProvider


@dataclass
class EventTraceExecutionResult:
    """Compact result returned after running an event trace workflow."""

    run_id: str
    report_path: str
    state_path: str
    run_dir: str
    output_path: str | None
    timeline_count: int
    supported_count: int
    single_source_count: int
    conflicted_count: int
    unsupported_count: int
    warning: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def source_from_arg(value: str) -> Source:
    """Create a Source from a URL, file:// URL, or local path."""

    path = Path(value).expanduser()
    if path.exists():
        return Source(url=str(path), title=path.name, source_type="file", relevance=1.0)
    return Source(url=value, title=value, source_type="seed", relevance=1.0)


def resolve_workspace_output_path(workspace_dir: Path, value: str) -> Path:
    """Resolve an output path and require it to stay inside the workspace."""

    workspace_root = workspace_dir.expanduser().resolve()
    candidate = Path(value).expanduser()
    if not candidate.is_absolute():
        candidate = workspace_root / candidate
    resolved = candidate.resolve()
    try:
        resolved.relative_to(workspace_root)
    except ValueError as exc:
        raise ValueError(f"Output path must stay inside workspace: {resolved}") from exc
    return resolved


def create_trace_llm_client(config: Config | None) -> LLMClient | None:
    """Create the configured LLM client for optional trace LLM steps."""

    if config is None:
        return None
    provider = LLMProvider.ANTHROPIC if config.llm.provider.lower() == "anthropic" else LLMProvider.OPENAI
    return LLMClient(
        api_key=config.llm.api_key,
        provider=provider,
        api_base=config.llm.api_base,
        model=config.llm.model,
    )


async def execute_event_trace(
    *,
    topic: str,
    workspace_dir: Path,
    config: Config | None = None,
    sources: list[str] | None = None,
    max_sources: int = 8,
    use_memory: bool = True,
    llm_plan: bool = False,
    llm_extract: bool = False,
    llm_judge: bool = False,
    output: str | None = None,
    json_output: str | None = None,
    run_id: str | None = None,
    research_depth: str = "quick",
    time_range: str | None = None,
    focus: list[str] | None = None,
) -> tuple[EventTraceExecutionResult, dict]:
    """Run the event trace workflow and persist report/state artifacts."""

    clean_topic = topic.strip()
    if not clean_topic:
        raise ValueError("topic is required")
    research_depth = research_depth if research_depth in {"quick", "deep"} else "quick"
    clean_focus = [item.strip() for item in focus or [] if item.strip()]
    if research_depth == "deep":
        llm_plan = True
        llm_judge = True

    workspace_dir = workspace_dir.expanduser().resolve()
    workspace_dir.mkdir(parents=True, exist_ok=True)

    tavily_api_key = os.environ.get("TAVILY_API_KEY", "")
    tavily_endpoint = "https://api.tavily.com/search"
    tavily_timeout = 20.0
    if config is not None:
        tavily_api_key = config.tools.web_search.api_key or tavily_api_key
        tavily_endpoint = config.tools.web_search.endpoint
        tavily_timeout = config.tools.web_search.timeout

    initial_sources = [source_from_arg(source) for source in sources or []]
    warning = None
    if not initial_sources and not tavily_api_key:
        warning = "No sources were provided and no Tavily API key is configured; the report may be empty."

    memory = EventTraceMemory(workspace_dir / ".event_trace_memory.jsonl") if use_memory else None
    planner_llm_client = create_trace_llm_client(config) if llm_plan else None
    extractor_llm_client = create_trace_llm_client(config) if llm_extract else None
    judge_llm_client = create_trace_llm_client(config) if llm_judge else None

    task_planner = ResponsibleTaskPlanner(
        memory=memory,
        llm_client=planner_llm_client,
        research_depth=research_depth,
        time_range=time_range,
        focus=clean_focus,
    )
    citation_judge = CitationJudge(llm_client=judge_llm_client)
    extractor = LLMEvidenceExtractor(extractor_llm_client) if extractor_llm_client else None

    run_id = run_id or datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    run_recorder = EventTraceRunRecorder(workspace_dir / ".event_trace" / "runs" / run_id, run_id=run_id)
    agent = EventTraceAgent(
        topic=clean_topic,
        search_provider=TavilySearchProvider(
            api_key=tavily_api_key,
            endpoint=tavily_endpoint,
            timeout=tavily_timeout,
        ),
        fetch_provider=DefaultPageFetcher(
            cache_dir=workspace_dir / ".event_trace" / "cache",
            timeout=tavily_timeout,
        ),
        evidence_extractor=extractor,
        task_planner=task_planner,
        citation_judge=citation_judge,
        run_recorder=run_recorder,
        memory=memory,
        initial_sources=initial_sources,
        max_sources=max_sources,
        max_search_rounds=3 if research_depth == "deep" else 2,
        research_depth=research_depth,
        time_range=time_range,
        focus=clean_focus,
    )
    state = await agent.run()
    report = state.get("report", "")

    output_path = None
    if output:
        output_path = resolve_workspace_output_path(workspace_dir, output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(report, encoding="utf-8")

    if json_output:
        json_path = resolve_workspace_output_path(workspace_dir, json_output)
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(state_to_jsonable(state), ensure_ascii=False, indent=2), encoding="utf-8")

    statuses = [item.validation_status for item in state.get("timeline", [])]
    result = EventTraceExecutionResult(
        run_id=run_id,
        report_path=str(run_recorder.report_file),
        state_path=str(run_recorder.state_file),
        run_dir=str(run_recorder.run_dir),
        output_path=str(output_path) if output_path else None,
        timeline_count=len(statuses),
        supported_count=statuses.count("supported"),
        single_source_count=statuses.count("single_source"),
        conflicted_count=statuses.count("conflicted"),
        unsupported_count=statuses.count("unsupported"),
        warning=warning,
    )
    return result, state
