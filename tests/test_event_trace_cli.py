from pathlib import Path
from types import SimpleNamespace

import pytest

from mini_agent.cli import _resolve_workspace_output_path, run_event_trace_eval


def test_resolve_workspace_output_path_keeps_relative_paths_in_workspace(tmp_path):
    result = _resolve_workspace_output_path(tmp_path, "reports/out.md")

    assert result == tmp_path / "reports" / "out.md"


def test_resolve_workspace_output_path_allows_absolute_path_inside_workspace(tmp_path):
    target = tmp_path / "reports" / "out.md"

    result = _resolve_workspace_output_path(tmp_path, str(target))

    assert result == target


def test_resolve_workspace_output_path_rejects_path_outside_workspace(tmp_path):
    outside = tmp_path.parent / "outside.md"

    with pytest.raises(ValueError, match="inside workspace"):
        _resolve_workspace_output_path(tmp_path, str(outside))


@pytest.mark.asyncio
async def test_run_event_trace_eval_writes_metrics(tmp_path):
    source = tmp_path / "source.txt"
    source.write_text("2024-01-01 Acme reported an outage.", encoding="utf-8")
    case_file = tmp_path / "case.json"
    case_file.write_text(
        """
{
  "topic": "Acme outage",
  "sources": ["source.txt"],
  "required_events": ["Acme reported outage"],
  "expected_citations": ["source.txt"]
}
""",
        encoding="utf-8",
    )
    args = SimpleNamespace(
        case_file=str(case_file),
        output="eval/result.json",
        llm_extract=False,
        llm_plan=False,
        llm_judge=False,
    )

    await run_event_trace_eval(args, tmp_path)

    result_file = tmp_path / "eval" / "result.json"
    assert result_file.exists()
    content = result_file.read_text(encoding="utf-8")
    assert "citation_coverage" in content
    assert (tmp_path / ".event_trace" / "evals").exists()
