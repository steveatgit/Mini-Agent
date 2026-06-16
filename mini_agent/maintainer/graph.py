"""LangGraph-style maintainer workflow nodes."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .artifacts import ArtifactWriter
from .implementer import ImplementerClient, run_model_implementer
from .patch_packager import render_plan, render_run_summary
from .planner import PlannerClient, render_structured_plan, run_model_context_select, run_model_patch_plan, run_model_triage
from .pr_writer import PRWriterClient, render_model_pr_description
from .reflector import ReflectorClient, reflect_on_failure
from .repo_inspector import (
    changed_files,
    create_patch,
    git_diff,
    render_repo_map,
    render_selected_context,
    scan_repo,
    select_context_files,
    triage_issue,
)
from .state import MaintainerState
from .verifier import render_test_results, run_verification


class MaintainerWorkflow:
    """Explicit workflow for issue-to-patch maintainer runs."""

    def __init__(
        self,
        repo_path: Path,
        artifacts: ArtifactWriter,
        *,
        verification_timeout: int = 120,
        max_retries: int = 2,
        use_langgraph: bool = True,
        planner_client: PlannerClient | None = None,
        implementer_client: ImplementerClient | None = None,
        verifier_client: ReflectorClient | None = None,
        pr_writer_client: PRWriterClient | None = None,
    ):
        self.repo_path = repo_path
        self.artifacts = artifacts
        self.verification_timeout = verification_timeout
        self.max_retries = max_retries
        self.use_langgraph = use_langgraph
        self.planner_client = planner_client
        self.implementer_client = implementer_client
        self.verifier_client = verifier_client
        self.pr_writer_client = pr_writer_client

    def run(self, state: MaintainerState) -> MaintainerState:
        """Run via LangGraph when installed, otherwise use the deterministic fallback."""

        if self.use_langgraph:
            graph = self._build_langgraph()
            if graph is not None:
                return graph.invoke(state)
        return self._run_fallback(state)

    def _build_langgraph(self) -> Any | None:
        try:
            from langgraph.graph import END, StateGraph
        except Exception:
            return None

        graph = StateGraph(MaintainerState)
        graph.add_node("bootstrap_run", self.bootstrap_run)
        graph.add_node("repo_scan", self.repo_scan)
        graph.add_node("issue_triage", self.issue_triage)
        graph.add_node("context_select", self.context_select)
        graph.add_node("plan_patch", self.plan_patch)
        graph.add_node("implement_patch", self.implement_patch)
        graph.add_node("run_verification", self.run_verification)
        graph.add_node("reflect_failure", self.reflect_failure)
        graph.add_node("package_artifacts", self.package_artifacts)

        graph.set_entry_point("bootstrap_run")
        graph.add_edge("bootstrap_run", "repo_scan")
        graph.add_edge("repo_scan", "issue_triage")
        graph.add_edge("issue_triage", "context_select")
        graph.add_edge("context_select", "plan_patch")
        graph.add_edge("plan_patch", "implement_patch")
        graph.add_edge("implement_patch", "run_verification")
        graph.add_conditional_edges(
            "run_verification",
            self._verification_route,
            {"retry": "reflect_failure", "package": "package_artifacts"},
        )
        graph.add_conditional_edges("reflect_failure", self._reflection_route, {"retry": "implement_patch", "package": "package_artifacts"})
        graph.add_edge("package_artifacts", END)
        return graph.compile()

    def _run_fallback(self, state: MaintainerState) -> MaintainerState:
        state = self.bootstrap_run(state)
        state = self.repo_scan(state)
        state = self.issue_triage(state)
        state = self.context_select(state)
        state = self.plan_patch(state)
        while True:
            state = self.implement_patch(state)
            state = self.run_verification(state)
            if self._verification_route(state) != "retry":
                break
            state = self.reflect_failure(state)
            if self._reflection_route(state) != "retry":
                break
        return self.package_artifacts(state)

    def bootstrap_run(self, state: MaintainerState) -> MaintainerState:
        self.artifacts.write_json(
            "input.json",
            {
                "repo_path": state.get("repo_path"),
                "issue_text": state.get("issue_text", ""),
                "test_command": state.get("test_command"),
                "constraints": state.get("constraints", []),
                "max_retries": self.max_retries,
            },
        )
        self.artifacts.append_trace({"node": "bootstrap_run", "repo_path": str(self.repo_path), "run_id": state.get("run_id")})
        return state

    def repo_scan(self, state: MaintainerState) -> MaintainerState:
        repo_map = scan_repo(self.repo_path)
        state["repo_map"] = repo_map
        if not state.get("test_command"):
            state["test_command"] = repo_map.get("detected_test_command")
        self.artifacts.write_text("repo_map.md", render_repo_map(repo_map))
        self.artifacts.append_trace({"node": "repo_scan", "file_count": len(repo_map.get("files", []))})
        return state

    def issue_triage(self, state: MaintainerState) -> MaintainerState:
        planner_error = None
        if self.planner_client is not None:
            payload, planner_error = run_model_triage(
                client=self.planner_client,
                issue_text=state.get("issue_text", ""),
                repo_map=state.get("repo_map", {}),
            )
            if payload is not None:
                triage = payload.model_dump()
            else:
                triage = triage_issue(state.get("issue_text", ""), state.get("repo_map", {}))
        else:
            triage = triage_issue(state.get("issue_text", ""), state.get("repo_map", {}))
        state["triage"] = triage
        state["suspected_files"] = list(triage.get("suspected_files", []))
        self.artifacts.write_json("triage.json", triage)
        self.artifacts.append_trace(
            {
                "node": "issue_triage",
                "mode": "llm" if self.planner_client is not None and planner_error is None else "fallback",
                "suspected_files": state["suspected_files"],
                "error": planner_error,
            }
        )
        return state

    def context_select(self, state: MaintainerState) -> MaintainerState:
        planner_error = None
        if self.planner_client is not None:
            payload, planner_error = run_model_context_select(
                client=self.planner_client,
                issue_text=state.get("issue_text", ""),
                repo_map=state.get("repo_map", {}),
                triage=state.get("triage", {}),
            )
            selected_files = payload.files if payload is not None else []
        else:
            selected_files = []
        if not selected_files:
            selected_files = select_context_files(state.get("issue_text", ""), state.get("repo_map", {}))
        if not selected_files:
            selected_files = state.get("suspected_files", [])
        state["suspected_files"] = selected_files
        context = render_selected_context(self.repo_path, selected_files)
        state["selected_context"] = context
        self.artifacts.write_text("selected_context.md", context)
        self.artifacts.append_trace(
            {
                "node": "context_select",
                "mode": "llm" if self.planner_client is not None and planner_error is None else "fallback",
                "selected_files": selected_files,
                "error": planner_error,
            }
        )
        return state

    def plan_patch(self, state: MaintainerState) -> MaintainerState:
        planner_error = None
        plan_payload: dict[str, Any] | None = None
        if self.planner_client is not None:
            payload, planner_error = run_model_patch_plan(
                client=self.planner_client,
                issue_text=state.get("issue_text", ""),
                triage=state.get("triage", {}),
                selected_files=state.get("suspected_files", []),
                selected_context=state.get("selected_context", ""),
                test_command=state.get("test_command"),
            )
            if payload is not None:
                plan_payload = payload.model_dump()
                plan = render_structured_plan(payload, state.get("test_command"))
            else:
                plan = render_plan(
                    state.get("issue_text", ""),
                    state.get("triage", {}),
                    state.get("suspected_files", []),
                    state.get("test_command"),
                )
        else:
            plan = render_plan(
                state.get("issue_text", ""),
                state.get("triage", {}),
                state.get("suspected_files", []),
                state.get("test_command"),
            )
        state["plan"] = plan
        if plan_payload is None:
            plan_payload = {
                "target_files": state.get("suspected_files", []),
                "changes": ["Use the deterministic fallback plan in plan.md."],
                "test_strategy": [f"Run `{state.get('test_command')}`."] if state.get("test_command") else [],
                "risks": ["Review generated artifacts before creating a PR."],
            }
        state["plan_payload"] = plan_payload
        self.artifacts.write_json("plan.json", plan_payload)
        self.artifacts.write_text("plan.md", plan)
        self.artifacts.append_trace(
            {
                "node": "plan_patch",
                "mode": "llm" if self.planner_client is not None and planner_error is None else "fallback",
                "test_command": state.get("test_command"),
                "target_files": plan_payload.get("target_files", []),
                "error": planner_error,
            }
        )
        return state

    def implement_patch(self, state: MaintainerState) -> MaintainerState:
        if self.implementer_client is not None:
            result = run_model_implementer(
                client=self.implementer_client,
                repo_path=self.repo_path,
                issue_text=state.get("issue_text", ""),
                triage=state.get("triage", {}),
                selected_context=state.get("selected_context", ""),
                plan=state.get("plan", ""),
                allowed_files=state.get("suspected_files", []),
                current_diff=git_diff(self.repo_path),
                failure_summary=state.get("failure_summary", ""),
            )
            notes = list(state.get("implementation_notes", []))
            if result.success:
                notes.append(f"Applied model patch touching: {', '.join(result.modified_files or []) or 'unknown'}")
            else:
                notes.append(f"Model patch failed: {result.error}")
            state["implementation_notes"] = notes
            self.artifacts.write_text("implementation.patch", result.patch)
            self.artifacts.append_trace(
                {
                    "node": "implement_patch",
                    "status": "applied" if result.success else "failed",
                    "retry_count": state.get("retry_count", 0),
                    "modified_files": result.modified_files or [],
                    "error": result.error,
                    "stderr": result.stderr[-2000:] if result.stderr else "",
                }
            )
            return state

        notes = list(state.get("implementation_notes", []))
        if not notes:
            notes.extend(
                [
                    "Deterministic MVP prepared repository context and artifacts.",
                    "Automatic implementation model is not enabled in this runner yet.",
                ]
            )
        state["implementation_notes"] = notes
        self.artifacts.append_trace({"node": "implement_patch", "status": "skipped", "retry_count": state.get("retry_count", 0)})
        return state

    def run_verification(self, state: MaintainerState) -> MaintainerState:
        test_result = run_verification(self.repo_path, state.get("test_command"), timeout=self.verification_timeout)
        results = list(state.get("test_results", []))
        results.append(test_result)
        state["test_results"] = results
        state["verification_status"] = test_result["status"]
        state["failure_summary"] = "" if test_result["status"] == "pass" else test_result["summary"]
        self.artifacts.write_text("test_results.md", render_test_results(results))
        self.artifacts.append_trace(
            {
                "node": "run_verification",
                "command": test_result.get("command"),
                "status": test_result.get("status"),
                "exit_code": test_result.get("exit_code"),
                "retry_count": state.get("retry_count", 0),
            }
        )
        return state

    def reflect_failure(self, state: MaintainerState) -> MaintainerState:
        retry_count = int(state.get("retry_count", 0)) + 1
        state["retry_count"] = retry_count
        reflection = reflect_on_failure(
            test_results=state.get("test_results", []),
            diff=git_diff(self.repo_path),
            plan=state.get("plan", ""),
            retry_count=retry_count,
            max_retries=self.max_retries,
            verifier_client=self.verifier_client,
            has_implementer=self.implementer_client is not None,
        )
        state["reflection"] = reflection.model_dump()
        state["failure_category"] = reflection.failure_category
        state["failure_summary"] = reflection.summary
        state["should_retry"] = reflection.should_retry
        note = f"Retry {retry_count}: {reflection.failure_category}: {reflection.summary}"
        notes = list(state.get("implementation_notes", []))
        notes.append(note)
        state["implementation_notes"] = notes
        self.artifacts.write_json("reflection.json", reflection.model_dump())
        self.artifacts.append_trace(
            {
                "node": "reflect_failure",
                "retry_count": retry_count,
                "failure_category": reflection.failure_category,
                "should_retry": reflection.should_retry,
                "failure_summary": reflection.summary,
            }
        )
        return state

    def package_artifacts(self, state: MaintainerState) -> MaintainerState:
        diff = git_diff(self.repo_path)
        patch = create_patch(self.repo_path)
        changed = changed_files(self.repo_path)
        state["diff"] = diff
        state["changed_files"] = changed
        self.artifacts.write_text("final.diff", diff + ("\n" if diff else ""))
        self.artifacts.write_text("final.patch", patch + ("\n" if patch else ""))

        pr_description, pr_writer_error = render_model_pr_description(
            client=self.pr_writer_client,
            issue_text=state.get("issue_text", ""),
            changed_files=changed,
            diff=diff,
            test_results=state.get("test_results", []),
            plan=state.get("plan", ""),
            failure_summary=state.get("failure_summary", ""),
        )
        state["pr_description"] = pr_description
        self.artifacts.write_text("pr_description.md", pr_description)

        summary = render_run_summary(state)
        state["final_report"] = summary
        state["artifacts_dir"] = str(self.artifacts.run_dir)
        self.artifacts.write_text("run_summary.md", summary)
        self.artifacts.write_json("state.json", state)
        self.artifacts.append_trace(
            {
                "node": "package_artifacts",
                "changed_files": changed,
                "status": state.get("verification_status"),
                "pr_writer_mode": "llm" if self.pr_writer_client is not None and pr_writer_error is None else "fallback",
                "error": pr_writer_error,
            }
        )
        return state

    def _verification_route(self, state: MaintainerState) -> str:
        if state.get("verification_status") == "pass":
            return "package"
        if int(state.get("retry_count", 0)) < self.max_retries:
            return "retry"
        return "package"

    def _reflection_route(self, state: MaintainerState) -> str:
        return "retry" if state.get("should_retry") else "package"
