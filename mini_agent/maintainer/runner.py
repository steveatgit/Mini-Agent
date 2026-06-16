"""Synchronous runner for the OSS maintainer workflow."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .artifacts import ArtifactWriter, make_run_id
from .graph import MaintainerWorkflow
from .implementer import ImplementerClient
from .repo_inspector import ensure_repo
from .state import MaintainerState


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
    max_retries: int = 0,
    use_langgraph: bool = True,
    implementer_client: ImplementerClient | None = None,
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
    workflow = MaintainerWorkflow(
        repo,
        artifacts,
        verification_timeout=verification_timeout,
        max_retries=max_retries,
        use_langgraph=use_langgraph,
        implementer_client=implementer_client,
    )
    state = workflow.run(state)

    return MaintainerRunResult(run_id=run_id, run_dir=artifacts.run_dir, status=state["verification_status"], state=state)
