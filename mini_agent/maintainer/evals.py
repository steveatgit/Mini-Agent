"""Local evaluation task loader for maintainer workflows."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class MaintainerEvalTask:
    """One local issue-to-patch evaluation task."""

    task_id: str
    task_dir: Path
    issue_text: str
    test_command: str | None = None
    expected_files: list[str] | None = None
    repo_ref: str | None = None


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
