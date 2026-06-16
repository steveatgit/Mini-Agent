"""Model-backed patch implementation helpers."""

from __future__ import annotations

import asyncio
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from mini_agent.schema import LLMResponse, Message, TokenUsage

from .prompts import PLAN_PATCH_PROMPT


class ImplementerClient(Protocol):
    async def generate(self, messages: list[Message], tools: list[Any] | None = None): ...


@dataclass
class PatchApplyResult:
    """Result of one implementer patch attempt."""

    success: bool
    patch: str = ""
    stdout: str = ""
    stderr: str = ""
    error: str = ""
    modified_files: list[str] | None = None
    usage: dict[str, int] | None = None


def run_model_implementer(
    *,
    client: ImplementerClient,
    repo_path: Path,
    issue_text: str,
    triage: dict[str, Any],
    selected_context: str,
    plan: str,
    allowed_files: list[str],
    current_diff: str = "",
    failure_summary: str = "",
) -> PatchApplyResult:
    """Ask an implementer model for a unified diff and apply it safely."""

    response = _generate_sync(
        client,
        [
            Message(role="system", content=_implementer_system_prompt()),
            Message(
                role="user",
                content=_implementer_user_prompt(
                    issue_text=issue_text,
                    triage=triage,
                    selected_context=selected_context,
                    plan=plan,
                    allowed_files=allowed_files,
                    current_diff=current_diff,
                    failure_summary=failure_summary,
                ),
            ),
        ],
    )
    patch = extract_unified_diff(str(response.content))
    if not patch:
        return PatchApplyResult(success=False, error="Implementer response did not contain a unified diff.", usage=_usage_dict(response.usage))
    result = apply_unified_diff(repo_path, patch, allowed_files=allowed_files)
    result.usage = _usage_dict(response.usage)
    return result


def extract_unified_diff(text: str) -> str:
    """Extract a unified diff from raw model text."""

    fenced = re.search(r"```(?:diff|patch)?\s*(diff --git .*?)```", text, flags=re.DOTALL)
    if fenced:
        return fenced.group(1).strip() + "\n"
    index = text.find("diff --git ")
    if index >= 0:
        return text[index:].strip() + "\n"
    return ""


def apply_unified_diff(repo_path: Path, patch: str, *, allowed_files: list[str]) -> PatchApplyResult:
    """Validate and apply a unified diff in repo_path."""

    modified_files = files_touched_by_patch(patch)
    disallowed = _disallowed_files(modified_files, allowed_files)
    if disallowed:
        return PatchApplyResult(
            success=False,
            patch=patch,
            error=f"Patch touches files outside the allowed plan: {', '.join(disallowed)}",
            modified_files=modified_files,
        )

    check = subprocess.run(["git", "-C", str(repo_path), "apply", "--check"], input=patch, capture_output=True, text=True)
    if check.returncode != 0:
        return PatchApplyResult(success=False, patch=patch, stdout=check.stdout, stderr=check.stderr, error="git apply --check failed", modified_files=modified_files)

    applied = subprocess.run(["git", "-C", str(repo_path), "apply"], input=patch, capture_output=True, text=True)
    if applied.returncode != 0:
        return PatchApplyResult(success=False, patch=patch, stdout=applied.stdout, stderr=applied.stderr, error="git apply failed", modified_files=modified_files)

    return PatchApplyResult(success=True, patch=patch, stdout=applied.stdout, stderr=applied.stderr, modified_files=modified_files)


def files_touched_by_patch(patch: str) -> list[str]:
    """Return repo-relative paths touched by a git unified diff."""

    files: list[str] = []
    for line in patch.splitlines():
        if line.startswith("diff --git "):
            parts = line.split()
            if len(parts) >= 4:
                files.extend(_clean_patch_path(path) for path in parts[2:4])
        elif line.startswith(("+++ ", "--- ")):
            parts = line.split(maxsplit=1)
            if len(parts) == 2 and parts[1] != "/dev/null":
                files.append(_clean_patch_path(parts[1]))
    return list(dict.fromkeys(path for path in files if path))


def _generate_sync(client: ImplementerClient, messages: list[Message]) -> LLMResponse:
    async def _call() -> LLMResponse:
        return await client.generate(messages=messages, tools=None)

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(_call())
    raise RuntimeError("Model implementer cannot run inside an active event loop in the synchronous maintainer runner.")


def _implementer_system_prompt() -> str:
    return (
        f"{PLAN_PATCH_PROMPT}\n\n"
        "You are the implementer node. Return only a git unified diff starting with 'diff --git'. "
        "Do not include prose. Keep the patch minimal and scoped to allowed files."
    )


def _implementer_user_prompt(
    *,
    issue_text: str,
    triage: dict[str, Any],
    selected_context: str,
    plan: str,
    allowed_files: list[str],
    current_diff: str,
    failure_summary: str,
) -> str:
    return "\n\n".join(
        [
            "# Issue",
            issue_text,
            "# Triage",
            str(triage),
            "# Allowed Files",
            "\n".join(f"- {path}" for path in allowed_files) or "- none",
            "# Plan",
            plan,
            "# Current Diff",
            current_diff or "(none)",
            "# Failure Summary",
            failure_summary or "(none)",
            "# Selected Context",
            selected_context,
        ]
    )


def _clean_patch_path(path: str) -> str:
    cleaned = path.strip()
    if cleaned.startswith("a/") or cleaned.startswith("b/"):
        cleaned = cleaned[2:]
    return cleaned


def _disallowed_files(modified_files: list[str], allowed_files: list[str]) -> list[str]:
    allowed = {path.strip().lstrip("/") for path in allowed_files if path.strip()}
    if not allowed:
        return modified_files
    return [path for path in modified_files if path not in allowed]


def _usage_dict(usage: TokenUsage | None) -> dict[str, int] | None:
    if usage is None:
        return None
    return {
        "prompt_tokens": usage.prompt_tokens,
        "completion_tokens": usage.completion_tokens,
        "total_tokens": usage.total_tokens,
    }
