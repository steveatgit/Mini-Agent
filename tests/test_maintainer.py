import json
import subprocess
from types import SimpleNamespace

from mini_agent.cli import run_maintainer_cli, run_maintainer_eval_cli
from mini_agent.maintainer import run_maintainer
from mini_agent.maintainer.evals import load_eval_task, load_eval_tasks, run_eval_tasks
from mini_agent.maintainer.implementer import apply_unified_diff, extract_unified_diff
from mini_agent.maintainer.prompts import ContextSelectionPayload, IssueTriagePayload
from mini_agent.maintainer.reflector import classify_failure, reflect_on_failure
from mini_agent.schema import LLMResponse


class FakePatchClient:
    def __init__(self, patch: str):
        self.patch = patch
        self.messages = []

    async def generate(self, messages, tools=None):
        self.messages.append(messages)
        return LLMResponse(content=f"```diff\n{self.patch}\n```", finish_reason="stop")


class FakeReflectClient:
    def __init__(self, payload: dict):
        self.payload = payload
        self.messages = []

    async def generate(self, messages, tools=None):
        self.messages.append(messages)
        return LLMResponse(content=json.dumps(self.payload), finish_reason="stop")


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
        llm_implement=False,
        llm_reflect=False,
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


def test_run_maintainer_with_fake_implementer_applies_patch(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    patch = """diff --git a/app.py b/app.py
--- a/app.py
+++ b/app.py
@@ -1,2 +1,2 @@
 def add(a, b):
-    return a + b
+    return int(a) + int(b)
"""

    result = run_maintainer(
        repo,
        "app.py add should coerce numeric strings\n\nExpected: tests pass.",
        test_command="python -m pytest tests/test_app.py",
        workspace_dir=tmp_path,
        run_id="llm-demo",
        use_langgraph=False,
        implementer_client=FakePatchClient(patch),
    )

    assert result.status == "pass"
    assert "int(a) + int(b)" in (repo / "app.py").read_text(encoding="utf-8")
    trace = (tmp_path / "artifacts" / "runs" / "llm-demo" / "tool_trace.jsonl").read_text(encoding="utf-8")
    assert '"status": "applied"' in trace


def test_run_maintainer_reflects_failed_verification_without_retry_loop(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)

    result = run_maintainer(
        repo,
        "app.py add should keep returning the sum\n\nExpected: tests pass.",
        test_command="python -c 'import sys; sys.exit(1)'",
        workspace_dir=tmp_path,
        run_id="reflect-demo",
        use_langgraph=False,
        max_retries=1,
    )

    run_dir = tmp_path / "artifacts" / "runs" / "reflect-demo"
    reflection = json.loads((run_dir / "reflection.json").read_text(encoding="utf-8"))
    assert result.status == "fail"
    assert result.state["retry_count"] == 1
    assert result.state["failure_category"] == "test_failed"
    assert reflection["should_retry"] is False
    assert len(result.state["test_results"]) == 1


def test_reflect_on_failure_uses_verifier_payload():
    client = FakeReflectClient(
        {
            "should_retry": True,
            "failure_category": "context_missing",
            "summary": "Need another file.",
            "next_steps": ["Select more context."],
        }
    )

    reflection = reflect_on_failure(
        test_results=[{"status": "fail", "exit_code": 1, "summary": "missing helper"}],
        diff="",
        plan="plan",
        retry_count=1,
        max_retries=2,
        verifier_client=client,
        has_implementer=True,
    )

    assert reflection.should_retry is True
    assert reflection.failure_category == "context_missing"
    assert client.messages


def test_classify_failure_categories():
    assert classify_failure({"status": "timeout"}) == "test_timeout"
    assert classify_failure({"status": "skipped"}) == "test_skipped"
    assert classify_failure({"status": "fail", "stderr": "ModuleNotFoundError: no module named x"}) == "dependency_missing"
    assert classify_failure({"status": "fail", "stderr": "git apply failed"}) == "patch_apply_failed"


def test_patch_apply_rejects_files_outside_plan(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    patch = """diff --git a/README.md b/README.md
--- a/README.md
+++ b/README.md
@@ -1 +1 @@
-# Demo
+# Changed
"""

    result = apply_unified_diff(repo, patch, allowed_files=["app.py"])

    assert not result.success
    assert "outside the allowed plan" in result.error
    assert (repo / "README.md").read_text(encoding="utf-8") == "# Demo\n"


def test_extract_unified_diff_from_fenced_model_response():
    text = "Here is the patch:\n```diff\ndiff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n@@ -1 +1 @@\n-a\n+b\n```"

    patch = extract_unified_diff(text)

    assert patch.startswith("diff --git")
    assert patch.endswith("\n")


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


def test_run_eval_tasks_writes_report_and_results(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    tasks_dir = tmp_path / "tasks"
    task_dir = tasks_dir / "task-001"
    task_dir.mkdir(parents=True)
    (task_dir / "issue.md").write_text("add should pass\n\nExpected: tests pass.", encoding="utf-8")
    (task_dir / "test_command.txt").write_text("python -m pytest tests/test_app.py\n", encoding="utf-8")
    (task_dir / "expected_files.txt").write_text("app.py\n", encoding="utf-8")

    result = run_eval_tasks(repo, tasks_dir, workspace_dir=tmp_path, output_dir=tmp_path / "eval-out", use_langgraph=False)

    assert result.metrics["total"] == 1
    assert result.metrics["test_pass_rate"] == 1.0
    assert (tmp_path / "eval-out" / "eval_report.md").exists()
    assert (tmp_path / "eval-out" / "eval_results.json").exists()


def test_run_maintainer_eval_cli(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    tasks_dir = tmp_path / "tasks"
    task_dir = tasks_dir / "task-001"
    task_dir.mkdir(parents=True)
    (task_dir / "issue.md").write_text("README task\n\nExpected: tests pass.", encoding="utf-8")
    args = SimpleNamespace(
        repo=str(repo),
        tasks_dir=str(tasks_dir),
        output_dir=str(tmp_path / "cli-eval-out"),
        test_command="python -m pytest tests/test_app.py",
        verification_timeout=120,
        max_retries=0,
        no_langgraph=True,
        llm_implement=False,
        llm_reflect=False,
    )

    run_maintainer_eval_cli(args, tmp_path)

    assert (tmp_path / "cli-eval-out" / "eval_report.md").exists()
    assert (tmp_path / "cli-eval-out" / "eval_results.json").exists()
