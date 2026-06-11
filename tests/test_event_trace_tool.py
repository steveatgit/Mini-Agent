import json

import pytest

from mini_agent.tools.event_trace_tool import EventTraceTool


@pytest.mark.asyncio
async def test_event_trace_tool_runs_from_local_sources(tmp_path):
    source_a = tmp_path / "source_a.txt"
    source_a.write_text(
        "2024-01-01 Acme reported a product outage after users could not log in. "
        "2024-01-02 Acme published an official response and said the service was restored.",
        encoding="utf-8",
    )
    source_b = tmp_path / "source_b.txt"
    source_b.write_text(
        "2024-01-01 Customers reported that Acme login service was unavailable.",
        encoding="utf-8",
    )
    tool = EventTraceTool(workspace_dir=str(tmp_path))

    result = await tool.execute(
        topic="Acme product outage",
        sources=[str(source_a), str(source_b)],
        use_memory=False,
    )

    assert result.success
    payload = json.loads(result.content)
    assert payload["timeline_count"] > 0
    assert payload["supported_count"] >= 1
    assert payload["report_path"].endswith("report.md")
    assert payload["state_path"].endswith("state.json")
    assert "summary" in payload


@pytest.mark.asyncio
async def test_event_trace_tool_rejects_output_outside_workspace(tmp_path):
    source = tmp_path / "source.txt"
    source.write_text("2024-01-01 Acme reported an outage.", encoding="utf-8")
    outside = tmp_path.parent / "outside.md"
    tool = EventTraceTool(workspace_dir=str(tmp_path))

    result = await tool.execute(
        topic="Acme outage",
        sources=[str(source)],
        output=str(outside),
        use_memory=False,
    )

    assert not result.success
    assert "inside workspace" in result.error


@pytest.mark.asyncio
async def test_event_trace_tool_deep_mode_writes_deep_report_sections(tmp_path):
    source_a = tmp_path / "source_a.txt"
    source_a.write_text(
        "2024-01-01 Acme reported a product outage after users could not log in. "
        "2024-01-02 Acme published an official response and said the service was restored.",
        encoding="utf-8",
    )
    source_b = tmp_path / "source_b.txt"
    source_b.write_text(
        "2024-01-01 Customers reported that Acme login service was unavailable. "
        "2024-01-03 A regulator said it was reviewing the Acme outage response.",
        encoding="utf-8",
    )
    tool = EventTraceTool(workspace_dir=str(tmp_path))

    result = await tool.execute(
        topic="Acme product outage",
        sources=[str(source_a), str(source_b)],
        research_depth="deep",
        time_range="2024-01",
        focus=["official response", "regulator review"],
        use_memory=False,
    )

    assert result.success
    payload = json.loads(result.content)
    report = (tmp_path / ".event_trace" / "runs" / payload["run_id"] / "report.md").read_text(encoding="utf-8")
    assert "# Event Deep Research Report: Acme product outage" in report
    assert "## Scope and Method" in report
    assert "## Evidence Table" in report
    assert "## Conflicts and Unverified Claims" in report
    assert "## Source Quality Notes" in report
    assert "## Open Questions" in report
    assert "Time range: 2024-01" in report
    assert "Focus: official response, regulator review" in report
