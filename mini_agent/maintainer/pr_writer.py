"""Model-backed PR description helpers for maintainer workflows."""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any, Protocol

from mini_agent.schema import Message

from .patch_packager import render_pr_description
from .prompts import PR_WRITER_PROMPT


class PRWriterClient(Protocol):
    async def generate(self, messages: list[Message], tools: list[Any] | None = None): ...


def render_model_pr_description(
    *,
    client: PRWriterClient | None,
    issue_text: str,
    changed_files: list[str],
    diff: str,
    test_results: list[dict[str, Any]],
    plan: str,
    failure_summary: str = "",
) -> tuple[str, str | None]:
    """Render a PR description with an optional model and deterministic fallback."""

    fallback = render_pr_description(issue_text, changed_files, test_results)
    if client is None:
        return fallback, None

    try:
        response_text = _generate_sync(
            client,
            [
                Message(role="system", content=_system_prompt()),
                Message(
                    role="user",
                    content=_user_prompt(
                        issue_text=issue_text,
                        changed_files=changed_files,
                        diff=diff,
                        test_results=test_results,
                        plan=plan,
                        failure_summary=failure_summary,
                    ),
                ),
            ],
        )
        description = _clean_markdown(response_text)
    except RuntimeError as exc:
        return fallback, str(exc)

    if not description:
        return fallback, "PR writer response was empty."
    return description, None


def _generate_sync(client: PRWriterClient, messages: list[Message]) -> str:
    async def _call() -> str:
        response = await client.generate(messages=messages, tools=None)
        return str(response.content)

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(_call())
    raise RuntimeError("PR writer model cannot run inside an active event loop in the synchronous maintainer runner.")


def _system_prompt() -> str:
    return (
        f"{PR_WRITER_PROMPT}\n\n"
        "Return only Markdown. Include these sections exactly: Summary, Issue Context, Key Changes, Verification, Risk and Rollback. "
        "Be concise and do not invent files or test results."
    )


def _user_prompt(
    *,
    issue_text: str,
    changed_files: list[str],
    diff: str,
    test_results: list[dict[str, Any]],
    plan: str,
    failure_summary: str,
) -> str:
    return "\n\n".join(
        [
            "# Issue",
            issue_text,
            "# Changed Files",
            "\n".join(f"- {path}" for path in changed_files) or "- none",
            "# Plan",
            plan or "(none)",
            "# Verification Results",
            json.dumps(test_results[-3:], ensure_ascii=False, indent=2),
            "# Failure Summary",
            failure_summary or "(none)",
            "# Diff",
            diff[:12000] or "(none)",
        ]
    )


def _clean_markdown(text: str) -> str:
    fenced = re.search(r"```(?:markdown|md)?\s*(.*?)```", text, flags=re.DOTALL)
    cleaned = fenced.group(1) if fenced else text
    cleaned = cleaned.strip()
    if not cleaned:
        return ""
    if not cleaned.startswith("#"):
        cleaned = "# PR Description\n\n" + cleaned
    return cleaned + "\n"
