"""Patch and report generation for maintainer runs."""

from __future__ import annotations

from typing import Any


def render_plan(issue_text: str, triage: dict[str, Any], selected_files: list[str], test_command: str | None) -> str:
    lines = [
        "# Patch Plan",
        "",
        "## Issue Summary",
        triage.get("summary") or issue_text.strip()[:500] or "(empty)",
        "",
        "## Target Files",
    ]
    if selected_files:
        lines.extend(f"- {path}" for path in selected_files)
    else:
        lines.append("- No specific files selected yet.")
    lines.extend(
        [
            "",
            "## Proposed Changes",
            "- Inspect the selected files against the issue description.",
            "- Keep edits scoped to the target files unless further evidence requires expanding scope.",
            "- Preserve existing public behavior outside the reported issue.",
            "",
            "## Test Strategy",
            f"- Run `{test_command}`." if test_command else "- No test command supplied or detected; package artifacts without verification.",
            "",
            "## Risks",
            "- This deterministic MVP does not yet invoke an implementation model, so code edits must come from an integrated agent step or manual changes before packaging.",
        ]
    )
    return "\n".join(lines) + "\n"


def render_pr_description(issue_text: str, changed_files: list[str], test_results: list[dict[str, Any]]) -> str:
    verification = test_results[-1] if test_results else {}
    lines = [
        "# PR Description",
        "",
        "## Summary",
        "- Address the reported maintainer task described in the linked issue.",
    ]
    if changed_files:
        lines.extend(f"- Updated `{path}`." for path in changed_files)
    else:
        lines.append("- No file changes were detected in this run.")
    lines.extend(
        [
            "",
            "## Issue",
            issue_text.strip() or "(empty)",
            "",
            "## Verification",
            f"- `{verification.get('command')}`: {verification.get('status')} (exit code: {verification.get('exit_code')})"
            if verification.get("command")
            else "- Verification was skipped.",
            "",
        "## Risk and Rollback",
        "- Review the generated diff before opening a PR.",
        "- Revert the patch from `final.patch` if verification or review finds regressions.",
    ]
    )
    return "\n".join(lines) + "\n"


def render_run_summary(state: dict[str, Any]) -> str:
    changed = state.get("changed_files", [])
    tests = state.get("test_results", [])
    latest_test = tests[-1] if tests else {}
    lines = [
        "# Run Summary",
        "",
        "## Task",
        state.get("issue_text", "").strip() or "(empty)",
        "",
        "## Result",
        f"- status: {state.get('verification_status', 'unknown')}",
        "- changed_files:",
    ]
    if changed:
        lines.extend(f"  - {path}" for path in changed)
    else:
        lines.append("  - none")
    lines.extend(
        [
            f"- retry_count: {state.get('retry_count', 0)}",
            "",
            "## Verification",
            f"- command: `{latest_test.get('command') or 'none'}`",
            f"- exit_code: {latest_test.get('exit_code')}",
            f"- summary: {latest_test.get('summary', 'No verification result.')}",
            "",
            "## Risk",
            "- The first maintainer MVP packages local changes and verification artifacts; automatic code implementation is intentionally narrow until the model node is wired in.",
            "",
            "## Next Steps",
            "- Review `final.diff` and `pr_description.md` before creating a PR.",
        ]
    )
    return "\n".join(lines) + "\n"
