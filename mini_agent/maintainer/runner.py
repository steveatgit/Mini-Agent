"""Synchronous runner for the OSS maintainer workflow."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .artifacts import ArtifactWriter, make_run_id
from .patch_packager import render_plan, render_pr_description, render_run_summary
from .repo_inspector import (
    changed_files,
    create_patch,
    ensure_repo,
    git_diff,
    render_repo_map,
    render_selected_context,
    scan_repo,
    select_context_files,
    triage_issue,
)
from .state import MaintainerState
from .verifier import render_test_results, run_verification


@dataclass
class MaintainerRunResult:
    """Paths and state produced by a maintainer run."""

    run_id: str
    run_dir: Path
    status: str
    state: MaintainerState


def run_maintainer(
    repo_path: str | Path,
    issue_text: str,
    *,
    test_command: str | None = None,
    workspace_dir: str | Path | None = None,
    run_id: str | None = None,
    constraints: list[str] | None = None,
    verification_timeout: int = 120,
) -> MaintainerRunResult:
    """Run the local maintainer workflow and write artifacts."""

    repo = ensure_repo(Path(repo_path))
    workspace = Path(workspace_dir).expanduser().resolve() if workspace_dir else repo
    run_id = run_id or make_run_id(issue_text.splitlines()[0] if issue_text.strip() else repo.name)
    artifacts = ArtifactWriter(workspace, run_id)

    state: MaintainerState = {
        "run_id": run_id,
        "repo_path": str(repo),
        "issue_text": issue_text,
        "constraints": constraints or [],
        "test_command": test_command,
        "retry_count": 0,
        "implementation_notes": [],
    }
    artifacts.write_json(
        "input.json",
        {
            "repo_path": str(repo),
            "issue_text": issue_text,
            "test_command": test_command,
            "constraints": constraints or [],
        },
    )

    artifacts.append_trace({"node": "bootstrap_run", "repo_path": str(repo), "run_id": run_id})

    repo_map = scan_repo(repo)
    state["repo_map"] = repo_map
    if not state.get("test_command"):
        state["test_command"] = repo_map.get("detected_test_command")
    artifacts.write_text("repo_map.md", render_repo_map(repo_map))
    artifacts.append_trace({"node": "repo_scan", "file_count": len(repo_map.get("files", []))})

    triage = triage_issue(issue_text, repo_map)
    state["triage"] = triage
    selected_files = select_context_files(issue_text, repo_map)
    state["suspected_files"] = selected_files
    context = render_selected_context(repo, selected_files)
    state["selected_context"] = context
    artifacts.write_json("triage.json", triage)
    artifacts.write_text("selected_context.md", context)
    artifacts.append_trace({"node": "issue_triage", "suspected_files": selected_files})

    plan = render_plan(issue_text, triage, selected_files, state.get("test_command"))
    state["plan"] = plan
    artifacts.write_text("plan.md", plan)
    artifacts.append_trace({"node": "plan_patch", "test_command": state.get("test_command")})

    state["implementation_notes"] = [
        "Deterministic MVP prepared repository context and artifacts.",
        "Automatic implementation model is not enabled in this runner yet.",
    ]
    artifacts.append_trace({"node": "implement_patch", "status": "skipped"})

    test_result = run_verification(repo, state.get("test_command"), timeout=verification_timeout)
    state["test_results"] = [test_result]
    state["verification_status"] = test_result["status"]
    state["failure_summary"] = "" if test_result["status"] == "pass" else test_result["summary"]
    artifacts.write_text("test_results.md", render_test_results(state["test_results"]))
    artifacts.append_trace(
        {
            "node": "run_verification",
            "command": test_result.get("command"),
            "status": test_result.get("status"),
            "exit_code": test_result.get("exit_code"),
        }
    )

    diff = git_diff(repo)
    patch = create_patch(repo)
    changed = changed_files(repo)
    state["diff"] = diff
    state["changed_files"] = changed
    artifacts.write_text("final.diff", diff + ("\n" if diff else ""))
    artifacts.write_text("final.patch", patch + ("\n" if patch else ""))

    pr_description = render_pr_description(issue_text, changed, state["test_results"])
    state["pr_description"] = pr_description
    artifacts.write_text("pr_description.md", pr_description)

    summary = render_run_summary(state)
    state["final_report"] = summary
    state["artifacts_dir"] = str(artifacts.run_dir)
    artifacts.write_text("run_summary.md", summary)
    artifacts.write_json("state.json", state)
    artifacts.append_trace({"node": "package_artifacts", "changed_files": changed, "status": state["verification_status"]})

    return MaintainerRunResult(run_id=run_id, run_dir=artifacts.run_dir, status=state["verification_status"], state=state)
