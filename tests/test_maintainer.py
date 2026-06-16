import subprocess
from types import SimpleNamespace

from mini_agent.cli import run_maintainer_cli
from mini_agent.maintainer import run_maintainer


def _init_repo(path):
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=path, check=True)
    (path / "README.md").write_text("# Demo\n", encoding="utf-8")
    (path / "app.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    tests_dir = path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_app.py").write_text(
        "from app import add\n\n\ndef test_add():\n    assert add(1, 2) == 3\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "."], cwd=path, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=path, check=True, capture_output=True, text=True)


def test_run_maintainer_writes_artifacts(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    issue = "add should keep returning the sum\n\nExpected: tests pass."

    result = run_maintainer(repo, issue, test_command="python -m pytest tests/test_app.py", workspace_dir=tmp_path, run_id="demo")

    assert result.status == "pass"
    assert (tmp_path / "artifacts" / "runs" / "demo" / "repo_map.md").exists()
    assert (tmp_path / "artifacts" / "runs" / "demo" / "test_results.md").exists()
    assert (tmp_path / "artifacts" / "runs" / "demo" / "final.patch").exists()
    summary = (tmp_path / "artifacts" / "runs" / "demo" / "run_summary.md").read_text(encoding="utf-8")
    assert "status: pass" in summary


def test_run_maintainer_cli_reads_issue_file(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    issue_file = tmp_path / "issue.md"
    issue_file.write_text("README task\n\nExpected: generate artifacts.", encoding="utf-8")
    args = SimpleNamespace(
        repo=str(repo),
        issue_file=str(issue_file),
        test_command=None,
        constraint=[],
        run_id="cli-demo",
        verification_timeout=120,
    )

    run_maintainer_cli(args, tmp_path)

    assert (tmp_path / "artifacts" / "runs" / "cli-demo" / "input.json").exists()
    assert (tmp_path / "artifacts" / "runs" / "cli-demo" / "pr_description.md").exists()
