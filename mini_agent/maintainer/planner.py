"""Model-backed planning helpers for maintainer workflows."""

from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from typing import Any, Protocol

from pydantic import ValidationError

from mini_agent.schema import Message

from .prompts import CONTEXT_SELECT_PROMPT, ISSUE_TRIAGE_PROMPT, PLAN_PATCH_PROMPT, ContextSelectionPayload, IssueTriagePayload, PatchPlanPayload


class PlannerClient(Protocol):
    async def generate(self, messages: list[Message], tools: list[Any] | None = None): ...


def run_model_triage(
    *,
    client: PlannerClient,
    issue_text: str,
    repo_map: dict[str, Any],
) -> tuple[IssueTriagePayload | None, str | None]:
    """Ask the planner model to classify the issue."""

    try:
        response_text = _generate_sync(
            client,
            [
                Message(role="system", content=f"{ISSUE_TRIAGE_PROMPT}\nReturn only valid JSON."),
                Message(role="user", content=_triage_user_prompt(issue_text, repo_map)),
            ],
        )
        return IssueTriagePayload.model_validate(_extract_json_object(response_text)), None
    except (RuntimeError, ValueError, ValidationError) as exc:
        return None, str(exc)


def run_model_context_select(
    *,
    client: PlannerClient,
    issue_text: str,
    repo_map: dict[str, Any],
    triage: dict[str, Any],
    max_files: int = 8,
) -> tuple[ContextSelectionPayload | None, str | None]:
    """Ask the planner model to select repo files, then keep only existing tracked files."""

    try:
        response_text = _generate_sync(
            client,
            [
                Message(role="system", content=f"{CONTEXT_SELECT_PROMPT}\nReturn only valid JSON."),
                Message(role="user", content=_context_user_prompt(issue_text, repo_map, triage, max_files)),
            ],
        )
        payload = ContextSelectionPayload.model_validate(_extract_json_object(response_text))
    except (RuntimeError, ValueError, ValidationError) as exc:
        return None, str(exc)

    repo_files = set(str(path) for path in repo_map.get("files", []))
    payload.files = [path for path in payload.files if path in repo_files][:max_files]
    if not payload.files:
        return None, "Planner context selection did not contain existing repository files."
    return payload, None


def run_model_patch_plan(
    *,
    client: PlannerClient,
    issue_text: str,
    triage: dict[str, Any],
    selected_files: list[str],
    selected_context: str,
    test_command: str | None,
) -> tuple[PatchPlanPayload | None, str | None]:
    """Ask the planner model for a structured patch plan."""

    try:
        response_text = _generate_sync(
            client,
            [
                Message(role="system", content=f"{PLAN_PATCH_PROMPT}\nReturn only valid JSON."),
                Message(
                    role="user",
                    content=_plan_user_prompt(
                        issue_text=issue_text,
                        triage=triage,
                        selected_files=selected_files,
                        selected_context=selected_context,
                        test_command=test_command,
                    ),
                ),
            ],
        )
        payload = PatchPlanPayload.model_validate(_extract_json_object(response_text))
    except (RuntimeError, ValueError, ValidationError) as exc:
        return None, str(exc)

    allowed = set(selected_files)
    payload.target_files = [path for path in payload.target_files if path in allowed] or list(selected_files)
    return payload, None


def render_structured_plan(payload: PatchPlanPayload, test_command: str | None) -> str:
    """Render a validated structured plan to Markdown."""

    lines = ["# Patch Plan", "", "## Target Files"]
    lines.extend(f"- {path}" for path in payload.target_files) if payload.target_files else lines.append("- No specific files selected yet.")
    lines.extend(["", "## Proposed Changes"])
    lines.extend(f"- {item}" for item in payload.changes) if payload.changes else lines.append("- Inspect selected files and apply the smallest viable fix.")
    lines.extend(["", "## Test Strategy"])
    if payload.test_strategy:
        lines.extend(f"- {item}" for item in payload.test_strategy)
    elif test_command:
        lines.append(f"- Run `{test_command}`.")
    else:
        lines.append("- No test command supplied or detected; package artifacts without verification.")
    lines.extend(["", "## Risks"])
    lines.extend(f"- {item}" for item in payload.risks) if payload.risks else lines.append("- Review the generated diff before opening a PR.")
    return "\n".join(lines) + "\n"


def _generate_sync(client: PlannerClient, messages: list[Message]) -> str:
    async def _call() -> str:
        response = await client.generate(messages=messages, tools=None)
        return str(response.content)

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(_call())
    raise RuntimeError("Planner model cannot run inside an active event loop in the synchronous maintainer runner.")


def _extract_json_object(text: str) -> dict[str, Any]:
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
    raw = fenced.group(1) if fenced else text
    start = raw.find("{")
    end = raw.rfind("}")
    if start < 0 or end < start:
        raise ValueError("Planner response did not contain a JSON object.")
    data = json.loads(raw[start : end + 1])
    if not isinstance(data, dict):
        raise ValueError("Planner response JSON must be an object.")
    return data


def _repo_brief(repo_map: dict[str, Any], max_files: int = 120) -> str:
    payload = {
        "languages": repo_map.get("languages", {}),
        "key_files": repo_map.get("key_files", []),
        "test_files": repo_map.get("test_files", [])[:40],
        "files": repo_map.get("files", [])[:max_files],
        "detected_test_command": repo_map.get("detected_test_command"),
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _triage_user_prompt(issue_text: str, repo_map: dict[str, Any]) -> str:
    return "\n\n".join(["# Issue", issue_text, "# Repository Map", _repo_brief(repo_map)])


def _context_user_prompt(issue_text: str, repo_map: dict[str, Any], triage: dict[str, Any], max_files: int) -> str:
    return "\n\n".join(
        [
            "# Issue",
            issue_text,
            "# Triage",
            json.dumps(triage, ensure_ascii=False, indent=2),
            "# Repository Map",
            _repo_brief(repo_map),
            f"Select at most {max_files} existing repo-relative files.",
        ]
    )


def _plan_user_prompt(
    *,
    issue_text: str,
    triage: dict[str, Any],
    selected_files: list[str],
    selected_context: str,
    test_command: str | None,
) -> str:
    return "\n\n".join(
        [
            "# Issue",
            issue_text,
            "# Triage",
            json.dumps(triage, ensure_ascii=False, indent=2),
            "# Selected Files",
            "\n".join(f"- {Path(path).as_posix()}" for path in selected_files) or "- none",
            "# Test Command",
            test_command or "(none)",
            "# Selected Context",
            selected_context,
        ]
    )
