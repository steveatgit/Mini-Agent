import json
import subprocess
import sys
from types import SimpleNamespace

from pathlib import Path

import pytest

from mini_agent.cli import parse_args, run_maintainer_cli, run_maintainer_eval_cli
from mini_agent.maintainer.artifacts import summarize_state_for_json
from mini_agent.maintainer import run_maintainer
from mini_agent.maintainer.evals import (
    MaintainerEvalRunResult,
    MaintainerEvalTaskResult,
    load_eval_task,
    load_eval_tasks,
    render_eval_report,
    run_eval_tasks,
)
from mini_agent.maintainer.implementer import apply_unified_diff, extract_unified_diff
from mini_agent.maintainer.planner import run_model_context_select
from mini_agent.maintainer.pr_writer import render_model_pr_description
from mini_agent.maintainer.prompts import ContextSelectionPayload, IssueTriagePayload
from mini_agent.maintainer.reflector import classify_failure, reflect_on_failure
from mini_agent.maintainer.repo_inspector import scan_repo
from mini_agent.schema import LLMResponse, TokenUsage


class FakePatchClient:
    def __init__(self, patch: str, usage: TokenUsage | None = None):
        self.patch = patch
        self.usage = usage
        self.messages = []

    async def generate(self, messages, tools=None):
        self.messages.append(messages)
        return LLMResponse(content=f"```diff\n{self.patch}\n```", finish_reason="stop", usage=self.usage)


class FakeReflectClient:
    def __init__(self, payload: dict, usage: TokenUsage | None = None):
        self.payload = payload
        self.usage = usage
        self.messages = []

    async def generate(self, messages, tools=None):
        self.messages.append(messages)
        return LLMResponse(content=json.dumps(self.payload), finish_reason="stop", usage=self.usage)


class FakePlanClient:
    def __init__(self, payloads: list[dict], usage: TokenUsage | None = None):
        self.payloads = list(payloads)
        self.usage = usage
        self.messages = []

    async def generate(self, messages, tools=None):
        self.messages.append(messages)
        return LLMResponse(content=json.dumps(self.payloads.pop(0)), finish_reason="stop", usage=self.usage)


class FakePRClient:
    def __init__(self, markdown: str, usage: TokenUsage | None = None):
        self.markdown = markdown
        self.usage = usage
        self.messages = []

    async def generate(self, messages, tools=None):
        self.messages.append(messages)
        return LLMResponse(content=self.markdown, finish_reason="stop", usage=self.usage)


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
        llm_plan=False,
        llm_implement=False,
        llm_reflect=False,
        llm_pr=False,
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


def test_run_maintainer_with_fake_planner_writes_structured_plan(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    planner = FakePlanClient(
        [
            {
                "issue_type": "bug",
                "summary": "add should support numeric strings",
                "keywords": ["add", "numeric"],
                "suspected_files": ["app.py", "tests/test_app.py"],
                "acceptance_criteria": ["tests pass"],
            },
            {"files": ["app.py", "missing.py", "tests/test_app.py"], "rationale": "implementation and coverage"},
            {
                "target_files": ["app.py", "tests/test_app.py"],
                "changes": ["Coerce add inputs before summing."],
                "test_strategy": ["Run the provided pytest command."],
                "risks": ["Low risk."],
            },
        ]
    )

    result = run_maintainer(
        repo,
        "app.py add should support numeric strings\n\nExpected: tests pass.",
        test_command="python -m pytest tests/test_app.py",
        workspace_dir=tmp_path,
        run_id="planner-demo",
        use_langgraph=False,
        planner_client=planner,
    )

    run_dir = tmp_path / "artifacts" / "runs" / "planner-demo"
    plan_json = json.loads((run_dir / "plan.json").read_text(encoding="utf-8"))
    trace = (run_dir / "tool_trace.jsonl").read_text(encoding="utf-8")
    assert result.status == "pass"
    assert plan_json["target_files"] == ["app.py", "tests/test_app.py"]
    assert "Coerce add inputs before summing." in (run_dir / "plan.md").read_text(encoding="utf-8")
    assert '"mode": "llm"' in trace


def test_run_maintainer_with_fake_pr_writer_writes_model_description(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    pr_writer = FakePRClient(
        "# PR Description\n\n"
        "## Summary\n- Model generated summary.\n\n"
        "## Issue Context\n- Covers the add issue.\n\n"
        "## Key Changes\n- No changes needed.\n\n"
        "## Verification\n- pytest passed.\n\n"
        "## Risk and Rollback\n- Revert final.patch if needed.\n"
    )

    result = run_maintainer(
        repo,
        "app.py add should keep returning the sum\n\nExpected: tests pass.",
        test_command="python -m pytest tests/test_app.py",
        workspace_dir=tmp_path,
        run_id="pr-demo",
        use_langgraph=False,
        pr_writer_client=pr_writer,
    )

    run_dir = tmp_path / "artifacts" / "runs" / "pr-demo"
    pr_description = (run_dir / "pr_description.md").read_text(encoding="utf-8")
    trace = (run_dir / "tool_trace.jsonl").read_text(encoding="utf-8")
    assert result.status == "pass"
    assert "Model generated summary." in pr_description
    assert '"pr_writer_mode": "llm"' in trace


def test_run_maintainer_run_summary_includes_timings_and_model_counts(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    planner = FakePlanClient(
        [
            {
                "issue_type": "bug",
                "summary": "add should support numeric strings",
                "keywords": ["add", "numeric"],
                "suspected_files": ["app.py", "tests/test_app.py"],
                "acceptance_criteria": ["tests pass"],
            },
            {"files": ["app.py", "tests/test_app.py"], "rationale": "implementation and coverage"},
            {
                "target_files": ["app.py", "tests/test_app.py"],
                "changes": ["Coerce add inputs before summing."],
                "test_strategy": ["Run the provided pytest command."],
                "risks": ["Low risk."],
            },
        ]
    )
    pr_writer = FakePRClient(
        "# PR Description\n\n"
        "## Summary\n- Model generated summary.\n\n"
        "## Issue Context\n- Covers the add issue.\n\n"
        "## Key Changes\n- No changes needed.\n\n"
        "## Verification\n- pytest passed.\n\n"
        "## Risk and Rollback\n- Revert final.patch if needed.\n"
    )

    result = run_maintainer(
        repo,
        "app.py add should support numeric strings\n\nExpected: tests pass.",
        test_command="python -m pytest tests/test_app.py",
        workspace_dir=tmp_path,
        run_id="summary-demo",
        use_langgraph=False,
        planner_client=planner,
        implementer_client=FakePatchClient(
            """diff --git a/app.py b/app.py
--- a/app.py
+++ b/app.py
@@ -1,2 +1,2 @@
 def add(a, b):
-    return a + b
+    return int(a) + int(b)
"""
        ),
        pr_writer_client=pr_writer,
    )

    run_dir = tmp_path / "artifacts" / "runs" / "summary-demo"
    summary = (run_dir / "run_summary.md").read_text(encoding="utf-8")
    state = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))

    assert result.status == "pass"
    assert "## Node Timings" in summary
    assert "## Model Calls" in summary
    assert state["node_timings"]["plan_patch"] >= 0
    assert state["model_call_counts"]["planner"] == 3
    assert state["model_call_counts"]["implementer"] == 1
    assert state["model_call_counts"]["pr_writer"] == 1


def test_run_maintainer_records_llm_token_usage(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    usage = TokenUsage(prompt_tokens=11, completion_tokens=7, total_tokens=18)
    planner = FakePlanClient(
        [
            {
                "issue_type": "bug",
                "summary": "add should support numeric strings",
                "keywords": ["add", "numeric"],
                "suspected_files": ["app.py", "tests/test_app.py"],
                "acceptance_criteria": ["tests pass"],
            },
            {"files": ["app.py", "tests/test_app.py"], "rationale": "implementation and coverage"},
            {
                "target_files": ["app.py", "tests/test_app.py"],
                "changes": ["Coerce add inputs before summing."],
                "test_strategy": ["Run the provided pytest command."],
                "risks": ["Low risk."],
            },
        ],
        usage=usage,
    )
    pr_writer = FakePRClient(
        "# PR Description\n\n## Summary\n- Model generated summary.\n",
        usage=usage,
    )

    result = run_maintainer(
        repo,
        "app.py add should support numeric strings\n\nExpected: tests pass.",
        test_command="python -m pytest tests/test_app.py",
        workspace_dir=tmp_path,
        run_id="usage-demo",
        use_langgraph=False,
        planner_client=planner,
        implementer_client=FakePatchClient(
            """diff --git a/app.py b/app.py
--- a/app.py
+++ b/app.py
@@ -1,2 +1,2 @@
 def add(a, b):
-    return a + b
+    return int(a) + int(b)
""",
            usage=usage,
        ),
        pr_writer_client=pr_writer,
    )

    run_dir = tmp_path / "artifacts" / "runs" / "usage-demo"
    summary = (run_dir / "run_summary.md").read_text(encoding="utf-8")

    assert result.status == "pass"
    assert result.state["llm_usage_total"]["total_tokens"] == 90
    assert result.state["llm_usage"]["planner"]["total_tokens"] == 54
    assert result.state["llm_usage"]["implementer"]["total_tokens"] == 18
    assert result.state["llm_usage"]["pr_writer"]["total_tokens"] == 18
    assert "## LLM Token Usage" in summary
    assert "total_tokens: 90" in summary


def test_summarize_state_for_json_truncates_large_payloads():
    payload = {
        "stdout": "x" * 5000,
        "test_results": [{"command": "pytest", "status": "fail", "exit_code": 1, "summary": "oops", "stdout": "y" * 4000, "stderr": "z" * 4000}],
        "nested": {"items": list(range(100))},
    }

    summarized = summarize_state_for_json(payload)

    assert len(summarized["stdout"]) < 1300
    assert "stdout" not in summarized["test_results"][0]
    assert len(summarized["nested"]["items"]) <= 61


def test_pr_writer_fallback_includes_rollback_guidance():
    markdown, error, usage = render_model_pr_description(
        client=None,
        issue_text="fix add",
        changed_files=["app.py"],
        diff="",
        test_results=[{"command": "pytest", "status": "pass", "exit_code": 0}],
        plan="plan",
    )

    assert error is None
    assert usage is None
    assert "Risk and Rollback" in markdown
    assert "Revert the patch" in markdown


def test_model_context_select_filters_to_existing_repo_files():
    client = FakePlanClient([{"files": ["/app.py", "../bad.py", "missing.py", "tests/test_app.py"], "rationale": "focused"}])
    payload, error, usage = run_model_context_select(
        client=client,
        issue_text="fix app",
        repo_map={"files": ["app.py", "tests/test_app.py"]},
        triage={},
    )

    assert error is None
    assert usage is None
    assert payload is not None
    assert payload.files == ["app.py", "tests/test_app.py"]


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


def test_run_maintainer_default_retries_reflect_once_without_implementer(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)

    result = run_maintainer(
        repo,
        "app.py add should keep returning the sum\n\nExpected: tests pass.",
        test_command="python -c 'import sys; sys.exit(1)'",
        workspace_dir=tmp_path,
        run_id="default-retry-demo",
        use_langgraph=False,
    )

    assert result.status == "fail"
    assert result.state["retry_count"] == 1
    assert result.state["failure_category"] == "test_failed"
    assert result.state["should_retry"] is False


def test_reflect_on_failure_uses_verifier_payload():
    client = FakeReflectClient(
        {
            "should_retry": True,
            "failure_category": "context_missing",
            "summary": "Need another file.",
            "next_steps": ["Select more context."],
        }
    )

    reflection, usage = reflect_on_failure(
        test_results=[{"status": "fail", "exit_code": 1, "summary": "missing helper"}],
        diff="",
        plan="plan",
        retry_count=1,
        max_retries=2,
        verifier_client=client,
        has_implementer=True,
    )

    assert usage is None
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

    assert {"python-cli-001", "python-cli-002", "docs-001", "failure-001"}.issubset(task_ids)
    task = load_eval_task("evals/tasks/python-cli-001")
    assert "argument parsing" in task.issue_text
    assert task.test_command == "python -m pytest tests/test_cli.py"
    assert task.expected_files == ["src/demo_cli.py", "tests/test_cli.py"]
    assert task.repo_ref == "python-cli-001"
    failure_task = load_eval_task("evals/tasks/failure-001")
    assert "verification step should fail" in failure_task.expected_behavior


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
        fixture_root=None,
        output_dir=str(tmp_path / "cli-eval-out"),
        test_command="python -m pytest tests/test_app.py",
        verification_timeout=120,
        max_retries=0,
        no_langgraph=True,
        llm_plan=False,
        llm_implement=False,
        llm_reflect=False,
        llm_pr=False,
    )

    run_maintainer_eval_cli(args, tmp_path)

    assert (tmp_path / "cli-eval-out" / "eval_report.md").exists()
    assert (tmp_path / "cli-eval-out" / "eval_results.json").exists()


def test_run_maintainer_eval_cli_with_fixture_root(tmp_path):
    fixture_root = tmp_path / "fixtures"
    task_root = tmp_path / "tasks"
    fixture_repo = fixture_root / "python-cli-001" / "repo"
    fixture_repo.mkdir(parents=True)
    (fixture_root / "python-cli-001" / "issue.md").write_text(
        "Fix empty CLI names.\n\nExpected: empty names raise a validation error.",
        encoding="utf-8",
    )
    (fixture_root / "python-cli-001" / "test_command.txt").write_text("PYTHONPATH=src python -m pytest tests/test_cli.py\n", encoding="utf-8")
    (fixture_root / "python-cli-001" / "expected_files.txt").write_text("src/demo_cli.py\ntests/test_cli.py\n", encoding="utf-8")
    (fixture_root / "python-cli-001" / "expected_behavior.md").write_text("Empty names must fail validation.", encoding="utf-8")
    (fixture_repo / "src").mkdir()
    (fixture_repo / "src/__init__.py").write_text("", encoding="utf-8")
    (fixture_repo / "src/demo_cli.py").write_text(
        "def greet(name):\n    return f\"Hello, {name}!\"\n",
        encoding="utf-8",
    )
    tests_dir = fixture_repo / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_cli.py").write_text(
        "import pytest\nfrom src.demo_cli import greet\n\n\ndef test_empty_name_raises():\n    with pytest.raises(ValueError):\n        greet(\"\")\n",
        encoding="utf-8",
    )
    task_dir = task_root / "python-cli-001"
    task_dir.mkdir(parents=True)
    (task_dir / "issue.md").write_text("Fix empty CLI names.\n\nExpected: empty names raise a validation error.", encoding="utf-8")
    (task_dir / "test_command.txt").write_text("PYTHONPATH=src python -m pytest tests/test_cli.py\n", encoding="utf-8")
    (task_dir / "expected_files.txt").write_text("src/demo_cli.py\ntests/test_cli.py\n", encoding="utf-8")
    (task_dir / "repo_ref.txt").write_text("python-cli-001\n", encoding="utf-8")
    patch = """diff --git a/src/demo_cli.py b/src/demo_cli.py
--- a/src/demo_cli.py
+++ b/src/demo_cli.py
@@ -1,2 +1,4 @@
 def greet(name):
-    return f"Hello, {name}!"
+    if not name:
+        raise ValueError("name is required")
+    return f"Hello, {name}!"
"""
    result = run_eval_tasks(
        repo_path=None,
        tasks_dir=task_root,
        workspace_dir=tmp_path,
        output_dir=tmp_path / "fixture-eval-out",
        fixture_root=fixture_root,
        use_langgraph=False,
        implementer_client=FakePatchClient(patch),
    )

    run_dir = tmp_path / "fixture-eval-out" / "artifacts" / "runs" / "eval-python-cli-001"
    assert result.metrics["total"] == 1
    assert result.task_results[0].status == "pass"
    assert result.task_results[0].repo_source.endswith("/python-cli-001/repo")
    summary = (run_dir / "run_summary.md").read_text(encoding="utf-8")
    state = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
    assert "## Node Timings" in summary
    assert "## Model Calls" in summary
    assert state["model_call_counts"]["implementer"] == 1


def test_run_eval_tasks_includes_failure_reason_for_failed_fixture(tmp_path):
    fixture_root = tmp_path / "fixtures"
    task_root = tmp_path / "tasks"
    fixture_repo = fixture_root / "failure-001" / "repo"
    fixture_repo.mkdir(parents=True)
    (fixture_root / "failure-001" / "issue.md").write_text(
        "Intentional failure fixture.\n\nExpected: the verification command fails.",
        encoding="utf-8",
    )
    (fixture_root / "failure-001" / "test_command.txt").write_text("python -c 'import sys; sys.exit(1)'\n", encoding="utf-8")
    (fixture_root / "failure-001" / "expected_files.txt").write_text("README.md\n", encoding="utf-8")
    (fixture_root / "failure-001" / "expected_behavior.md").write_text(
        "The verification step should fail with exit code 1 so the report can explain the failure path.",
        encoding="utf-8",
    )
    (fixture_repo / "README.md").write_text("# Failure Fixture\n", encoding="utf-8")
    task_dir = task_root / "failure-001"
    task_dir.mkdir(parents=True)
    (task_dir / "issue.md").write_text("Intentional failure fixture.\n\nExpected: the verification command fails.", encoding="utf-8")
    (task_dir / "test_command.txt").write_text("python -c 'import sys; sys.exit(1)'\n", encoding="utf-8")
    (task_dir / "expected_files.txt").write_text("README.md\n", encoding="utf-8")
    (task_dir / "expected_behavior.md").write_text(
        "The verification step should fail with exit code 1 so the report can explain the failure path.",
        encoding="utf-8",
    )
    (task_dir / "repo_ref.txt").write_text("failure-001\n", encoding="utf-8")

    result = run_eval_tasks(
        repo_path=None,
        tasks_dir=task_root,
        workspace_dir=tmp_path,
        output_dir=tmp_path / "failure-eval-out",
        fixture_root=fixture_root,
        use_langgraph=False,
    )

    run_dir = tmp_path / "failure-eval-out" / "artifacts" / "runs" / "eval-failure-001"
    report = (tmp_path / "failure-eval-out" / "eval_report.md").read_text(encoding="utf-8")

    assert result.task_results[0].status == "fail"
    assert result.task_results[0].failure_category == "test_failed"
    assert "The verification step should fail" in report
    assert "failure_summary" in report
    assert "Command failed with exit code 1" in result.task_results[0].failure_summary
    assert run_dir.exists()


def test_scan_repo_detects_key_files_and_tests(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    (repo / "pyproject.toml").write_text("[tool.pytest.ini_options]\n", encoding="utf-8")
    subprocess.run(["git", "add", "pyproject.toml"], cwd=repo, check=True, capture_output=True, text=True)

    repo_map = scan_repo(repo)

    assert repo_map["detected_test_command"] == "pytest"
    assert "pyproject.toml" in repo_map["key_files"]
    assert "tests/test_app.py" in repo_map["test_files"]


def test_run_maintainer_verification_timeout_records_timeout(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)

    result = run_maintainer(
        repo,
        "add should keep returning the sum\n\nExpected: tests pass.",
        test_command="python -c 'import time; time.sleep(1.5)'",
        workspace_dir=tmp_path,
        run_id="timeout-demo",
        use_langgraph=False,
        verification_timeout=1,
    )

    assert result.status == "timeout"
    assert result.state["verification_status"] == "timeout"
    assert result.state["test_results"][-1]["status"] == "timeout"
    assert "timed out" in result.state["test_results"][-1]["summary"]


def test_cli_parse_args_handles_maintainer_commands(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "mini-agent",
            "maintain-eval",
            "--fixture-root",
            "evals/fixtures",
            "--tasks-dir",
            "evals/tasks",
            "--no-langgraph",
            "--llm-pr",
        ],
    )

    args = parse_args()

    assert args.command == "maintain-eval"
    assert args.fixture_root == "evals/fixtures"
    assert args.no_langgraph is True
    assert args.llm_pr is True


def test_render_eval_report_includes_failure_and_repo_source(tmp_path):
    run_result = MaintainerEvalRunResult(
        tasks_dir=tmp_path / "tasks",
        repo_path=None,
        output_dir=tmp_path / "out",
        task_results=[
            MaintainerEvalTaskResult(
                task_id="failure-001",
                status="fail",
                run_id="eval-failure-001",
                run_dir=tmp_path / "out" / "artifacts" / "runs" / "eval-failure-001",
                repo_source="/tmp/fixtures/failure-001/repo",
                expected_behavior="The verification step should fail with exit code 1 so the report can explain the failure path.",
                changed_files=[],
                expected_files=["README.md"],
                test_command="python -c 'import sys; sys.exit(1)'",
                failure_summary="Command failed with exit code 1 and no output.",
                failure_category="test_failed",
                retry_count=0,
                prompt_tokens=11,
                completion_tokens=7,
                total_tokens=18,
                node_duration_seconds=0.42,
            )
        ],
    )

    report = render_eval_report(run_result)

    assert "failure-001" in report
    assert "repo_source: /tmp/fixtures/failure-001/repo" in report
    assert "failure_summary: Command failed with exit code 1 and no output." in report
    assert "expected_behavior: The verification step should fail" in report
    assert "avg_tokens: 18.00" in report
    assert "avg_duration_seconds: 0.42" in report
    assert "total_tokens_total: 18" in report
