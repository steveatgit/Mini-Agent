import subprocess
from types import SimpleNamespace

from mini_agent.cli import run_maintainer_cli
from mini_agent.maintainer import run_maintainer
from mini_agent.maintainer.evals import load_eval_task, load_eval_tasks
from mini_agent.maintainer.prompts import ContextSelectionPayload, IssueTriagePayload


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
        max_retries=0,
        no_langgraph=True,
    )

    run_maintainer_cli(args, tmp_path)

    assert (tmp_path / "artifacts" / "runs" / "cli-demo" / "input.json").exists()
    assert (tmp_path / "artifacts" / "runs" / "cli-demo" / "pr_description.md").exists()


def test_run_maintainer_fallback_workflow_writes_trace(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    issue = "add should keep returning the sum\n\nExpected: tests pass."

    result = run_maintainer(
        repo,
        issue,
        test_command="python -m pytest tests/test_app.py",
        workspace_dir=tmp_path,
        run_id="fallback-demo",
        use_langgraph=False,
    )

    trace = (tmp_path / "artifacts" / "runs" / "fallback-demo" / "tool_trace.jsonl").read_text(encoding="utf-8")
    assert result.status == "pass"
    assert '"node": "context_select"' in trace
    assert '"node": "package_artifacts"' in trace


def test_prompt_payloads_clean_model_outputs():
    triage = IssueTriagePayload(
        issue_type="BUG",
        summary="  Broken behavior  ",
        keywords=["parser", "parser", ""],
        suspected_files=["src/parser.py", "src/parser.py"],
        acceptance_criteria=[" should pass "],
    )
    context = ContextSelectionPayload(files=["/src/parser.py", "../bad.py", "tests/test_parser.py"], rationale="  focused  ")

    assert triage.issue_type == "bug"
    assert triage.keywords == ["parser"]
    assert context.files == ["src/parser.py", "tests/test_parser.py"]
    assert context.rationale == "focused"


def test_load_eval_tasks_from_fixture_directory():
    tasks = load_eval_tasks("evals/tasks")
    task_ids = {task.task_id for task in tasks}

    assert {"python-cli-001", "python-cli-002", "docs-001"}.issubset(task_ids)
    task = load_eval_task("evals/tasks/python-cli-001")
    assert "argument parsing" in task.issue_text
    assert task.test_command == "python -m pytest tests/test_cli.py"
    assert task.expected_files == ["src/demo_cli.py", "tests/test_cli.py"]
