"""Local evaluation task loader for maintainer workflows."""

from __future__ import annotations

import json
import shutil
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any
import subprocess

from .implementer import ImplementerClient
from .planner import PlannerClient
from .pr_writer import PRWriterClient
from .reflector import ReflectorClient
from .runner import MaintainerRunResult, run_maintainer


@dataclass
class MaintainerEvalTask:
    """One local issue-to-patch evaluation task."""

    task_id: str
    task_dir: Path
    issue_text: str
    test_command: str | None = None
    expected_files: list[str] | None = None
    expected_behavior: str | None = None
    repo_ref: str | None = None


@dataclass
class MaintainerEvalTaskResult:
    """Result for one local maintainer eval task."""

    task_id: str
    status: str
    run_id: str
    run_dir: Path
    repo_source: str | None
    changed_files: list[str]
    expected_files: list[str]
    test_command: str | None
    failure_category: str
    retry_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "status": self.status,
            "run_id": self.run_id,
            "run_dir": str(self.run_dir),
            "repo_source": self.repo_source,
            "changed_files": self.changed_files,
            "expected_files": self.expected_files,
            "test_command": self.test_command,
            "failure_category": self.failure_category,
            "retry_count": self.retry_count,
        }


@dataclass
class MaintainerEvalRunResult:
    """Aggregate result for a local maintainer eval run."""

    tasks_dir: Path
    repo_path: Path | None
    output_dir: Path
    task_results: list[MaintainerEvalTaskResult]

    @property
    def metrics(self) -> dict[str, Any]:
        total = len(self.task_results)
        pass_count = sum(1 for result in self.task_results if result.status == "pass")
        failure_categories: dict[str, int] = {}
        retry_total = 0
        for result in self.task_results:
            retry_total += result.retry_count
            if result.status != "pass":
                category = result.failure_category or "unknown"
                failure_categories[category] = failure_categories.get(category, 0) + 1
        return {
            "total": total,
            "resolved_rate": pass_count / total if total else 0.0,
            "test_pass_rate": pass_count / total if total else 0.0,
            "avg_iterations": retry_total / total if total else 0.0,
            "failure_categories": failure_categories,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "tasks_dir": str(self.tasks_dir),
            "repo_path": str(self.repo_path) if self.repo_path else None,
            "output_dir": str(self.output_dir),
            "metrics": self.metrics,
            "tasks": [result.to_dict() for result in self.task_results],
        }


def load_eval_task(task_dir: str | Path) -> MaintainerEvalTask:
    """Load a maintainer eval task from a directory."""

    path = Path(task_dir).expanduser().resolve()
    if not path.exists() or not path.is_dir():
        raise ValueError(f"Eval task directory does not exist: {path}")

    issue_path = path / "issue.md"
    if not issue_path.exists():
        raise ValueError(f"Eval task is missing issue.md: {path}")

    return MaintainerEvalTask(
        task_id=path.name,
        task_dir=path,
        issue_text=issue_path.read_text(encoding="utf-8"),
        test_command=_read_optional(path / "test_command.txt"),
        expected_files=_read_lines(path / "expected_files.txt"),
        expected_behavior=_read_optional(path / "expected_behavior.md"),
        repo_ref=_read_optional(path / "repo_ref.txt"),
    )


def load_eval_tasks(root_dir: str | Path) -> list[MaintainerEvalTask]:
    """Load all eval task directories under root_dir."""

    root = Path(root_dir).expanduser().resolve()
    if not root.exists():
        return []
    tasks = []
    for child in sorted(root.iterdir()):
        if child.is_dir() and (child / "issue.md").exists():
            tasks.append(load_eval_task(child))
    return tasks


def run_eval_tasks(
    repo_path: str | Path | None,
    tasks_dir: str | Path,
    *,
    workspace_dir: str | Path,
    output_dir: str | Path | None = None,
    fixture_root: str | Path | None = None,
    verification_timeout: int = 120,
    max_retries: int = 2,
    use_langgraph: bool = True,
    test_command_override: str | None = None,
    planner_client: PlannerClient | None = None,
    implementer_client: ImplementerClient | None = None,
    verifier_client: ReflectorClient | None = None,
    pr_writer_client: PRWriterClient | None = None,
) -> MaintainerEvalRunResult:
    """Run maintainer workflow over all local eval tasks."""

    repo = Path(repo_path).expanduser().resolve() if repo_path is not None else None
    fixture_root_path = Path(fixture_root).expanduser().resolve() if fixture_root else None
    tasks_root = Path(tasks_dir).expanduser().resolve()
    workspace = Path(workspace_dir).expanduser().resolve()
    out_dir = Path(output_dir).expanduser().resolve() if output_dir else workspace / "artifacts" / "evals" / tasks_root.name
    out_dir.mkdir(parents=True, exist_ok=True)

    tasks = load_eval_tasks(tasks_root)
    task_results: list[MaintainerEvalTaskResult] = []
    for task in tasks:
        test_command = test_command_override or task.test_command
        with _resolve_task_repo(task, repo, fixture_root_path, out_dir) as task_repo:
            run_result = run_maintainer(
                task_repo,
                task.issue_text,
                test_command=test_command,
                workspace_dir=out_dir,
                run_id=f"eval-{task.task_id}",
                constraints=[f"eval_task_id={task.task_id}"],
                verification_timeout=verification_timeout,
                max_retries=max_retries,
                use_langgraph=use_langgraph,
                planner_client=planner_client,
                implementer_client=implementer_client,
                verifier_client=verifier_client,
                pr_writer_client=pr_writer_client,
            )
        task_results.append(_task_result_from_run(task, run_result, test_command, repo_source=_repo_source_label(task, repo, fixture_root_path)))

    result = MaintainerEvalRunResult(tasks_dir=tasks_root, repo_path=repo, output_dir=out_dir, task_results=task_results)
    (out_dir / "eval_results.json").write_text(json.dumps(result.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "eval_report.md").write_text(render_eval_report(result), encoding="utf-8")
    return result


def render_eval_report(result: MaintainerEvalRunResult) -> str:
    """Render aggregate eval metrics as Markdown."""

    metrics = result.metrics
    lines = [
        "# Maintainer Eval Report",
        "",
        f"- repo_path: {result.repo_path or 'fixture-root'}",
        f"- tasks_dir: {result.tasks_dir}",
        f"- total: {metrics['total']}",
        f"- resolved_rate: {metrics['resolved_rate']:.2f}",
        f"- test_pass_rate: {metrics['test_pass_rate']:.2f}",
        f"- avg_iterations: {metrics['avg_iterations']:.2f}",
        "",
        "## Failure Categories",
    ]
    failure_categories = metrics["failure_categories"]
    if failure_categories:
        lines.extend(f"- {category}: {count}" for category, count in sorted(failure_categories.items()))
    else:
        lines.append("- none")
    lines.extend(["", "## Tasks", ""])
    for task in result.task_results:
        lines.extend(
            [
                f"### {task.task_id}",
                "",
                f"- status: {task.status}",
                f"- run_id: {task.run_id}",
                f"- test_command: `{task.test_command or 'none'}`",
                f"- retry_count: {task.retry_count}",
                f"- repo_source: {task.repo_source or 'unknown'}",
                f"- changed_files: {', '.join(task.changed_files) if task.changed_files else 'none'}",
                f"- expected_files: {', '.join(task.expected_files) if task.expected_files else 'none'}",
                f"- failure_category: {task.failure_category or 'none'}",
                "",
            ]
        )
    return "\n".join(lines)


def _read_optional(path: Path) -> str | None:
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8").strip()
    return text or None


def _read_lines(path: Path) -> list[str] | None:
    if not path.exists():
        return None
    lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines()]
    cleaned = [line for line in lines if line and not line.startswith("#")]
    return cleaned or None


def _task_result_from_run(
    task: MaintainerEvalTask,
    run_result: MaintainerRunResult,
    test_command: str | None,
    *,
    repo_source: str | None,
) -> MaintainerEvalTaskResult:
    state = run_result.state
    return MaintainerEvalTaskResult(
        task_id=task.task_id,
        status=run_result.status,
        run_id=run_result.run_id,
        run_dir=run_result.run_dir,
        repo_source=repo_source,
        changed_files=list(state.get("changed_files", [])),
        expected_files=task.expected_files or [],
        test_command=test_command,
        failure_category=_failure_category(state),
        retry_count=int(state.get("retry_count", 0)),
    )


def _failure_category(state: dict[str, Any]) -> str:
    if state.get("failure_category"):
        return str(state["failure_category"])
    if state.get("verification_status") == "pass":
        return ""
    latest = (state.get("test_results") or [{}])[-1]
    status = latest.get("status")
    if status == "timeout":
        return "test_timeout"
    if status == "skipped":
        return "test_skipped"
    if latest.get("exit_code") not in {0, None}:
        return "test_failed"
    return "unknown"


def _repo_source_label(task: MaintainerEvalTask, repo_path: Path | None, fixture_root: Path | None) -> str | None:
    if fixture_root is not None:
        repo_ref = task.repo_ref or task.task_id
        return str(fixture_root / repo_ref / "repo")
    if repo_path is not None:
        return str(repo_path)
    return None


@contextmanager
def _resolve_task_repo(
    task: MaintainerEvalTask,
    repo_path: Path | None,
    fixture_root: Path | None,
    out_dir: Path,
):
    if fixture_root is None:
        if repo_path is None:
            raise ValueError("Either repo_path or fixture_root must be provided for maintainer eval.")
        yield repo_path
        return

    repo_ref = task.repo_ref or task.task_id
    fixture_repo = fixture_root / repo_ref / "repo"
    if not fixture_repo.exists() or not fixture_repo.is_dir():
        raise ValueError(f"Fixture repo does not exist: {fixture_repo}")

    temp_root = out_dir / "_fixture_repos"
    temp_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f"{task.task_id}-", dir=str(temp_root)) as tmpdir:
        copied_repo = Path(tmpdir) / "repo"
        shutil.copytree(fixture_repo, copied_repo)
        subprocess.run(["git", "init"], cwd=copied_repo, capture_output=True, text=True, check=True)
        yield copied_repo
