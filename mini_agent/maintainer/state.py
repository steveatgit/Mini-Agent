"""State types for the OSS maintainer workflow."""

from __future__ import annotations

from typing import Any, TypedDict


class MaintainerState(TypedDict, total=False):
    """Graph state for a repository maintenance run."""

    run_id: str
    repo_path: str
    issue_text: str
    constraints: list[str]
    test_command: str | None

    repo_map: dict[str, Any]
    triage: dict[str, Any]
    suspected_files: list[str]
    plan: str
    selected_context: str
    implementation_notes: list[str]

    changed_files: list[str]
    diff: str
    test_results: list[dict[str, Any]]
    verification_status: str
    failure_summary: str
    failure_category: str
    reflection: dict[str, Any]
    should_retry: bool
    retry_count: int

    pr_description: str
    artifacts_dir: str
    final_report: str
