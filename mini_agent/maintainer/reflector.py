"""Failure reflection helpers for maintainer workflows."""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any, Protocol

from mini_agent.schema import Message

from .prompts import FAILURE_REFLECTION_PROMPT, FailureReflectionPayload


class ReflectorClient(Protocol):
    async def generate(self, messages: list[Message], tools: list[Any] | None = None): ...


def reflect_on_failure(
    *,
    test_results: list[dict[str, Any]],
    diff: str,
    plan: str,
    retry_count: int,
    max_retries: int,
    verifier_client: ReflectorClient | None = None,
    has_implementer: bool = False,
) -> FailureReflectionPayload:
    """Classify a verification failure and decide whether another attempt is useful."""

    latest = test_results[-1] if test_results else {}
    fallback = deterministic_reflection(
        latest_result=latest,
        retry_count=retry_count,
        max_retries=max_retries,
        has_implementer=has_implementer,
    )
    if verifier_client is None:
        return fallback

    try:
        response_text = _generate_sync(
            verifier_client,
            [
                Message(role="system", content=_reflector_system_prompt()),
                Message(
                    role="user",
                    content=_reflector_user_prompt(
                        latest_result=latest,
                        diff=diff,
                        plan=plan,
                        retry_count=retry_count,
                        max_retries=max_retries,
                    ),
                ),
            ],
        )
        payload = FailureReflectionPayload.model_validate(_extract_json_object(response_text))
    except Exception as exc:
        return FailureReflectionPayload(
            should_retry=fallback.should_retry,
            failure_category="model_format_error",
            summary=f"Verifier reflection failed to produce valid JSON: {exc}",
            next_steps=fallback.next_steps,
        )

    if retry_count >= max_retries:
        payload.should_retry = False
    return payload


def deterministic_reflection(
    *,
    latest_result: dict[str, Any],
    retry_count: int,
    max_retries: int,
    has_implementer: bool,
) -> FailureReflectionPayload:
    """Rule-based fallback reflection for verification failures."""

    category = classify_failure(latest_result)
    should_retry = has_implementer and retry_count < max_retries and category in {"test_failed", "patch_apply_failed", "context_missing"}
    summary = latest_result.get("summary") or "Verification failed without a detailed summary."
    next_steps = _next_steps_for_category(category)
    return FailureReflectionPayload(
        should_retry=should_retry,
        failure_category=category,
        summary=str(summary)[:800],
        next_steps=next_steps,
    )


def classify_failure(latest_result: dict[str, Any]) -> str:
    """Classify a failed verification result."""

    status = latest_result.get("status")
    summary = str(latest_result.get("summary") or "")
    stderr = str(latest_result.get("stderr") or "")
    stdout = str(latest_result.get("stdout") or "")
    combined = "\n".join([summary, stderr, stdout]).lower()
    if status == "timeout":
        return "test_timeout"
    if status == "skipped":
        return "test_skipped"
    if any(marker in combined for marker in ("modulenotfounderror", "no module named", "command not found", "no such file or directory")):
        return "dependency_missing"
    if "git apply" in combined or "patch" in combined and "failed" in combined:
        return "patch_apply_failed"
    if any(marker in combined for marker in ("file not found", "unknown file", "cannot find")):
        return "context_missing"
    if latest_result.get("exit_code") not in {0, None} or status == "fail":
        return "test_failed"
    return "unknown"


def _generate_sync(client: ReflectorClient, messages: list[Message]) -> str:
    async def _call() -> str:
        response = await client.generate(messages=messages, tools=None)
        return str(response.content)

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(_call())
    raise RuntimeError("Failure reflector cannot run inside an active event loop in the synchronous maintainer runner.")


def _extract_json_object(text: str) -> dict[str, Any]:
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
    raw = fenced.group(1) if fenced else text
    if "{" in raw and "}" in raw:
        raw = raw[raw.find("{") : raw.rfind("}") + 1]
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("reflection payload must be a JSON object")
    return data


def _reflector_system_prompt() -> str:
    return (
        f"{FAILURE_REFLECTION_PROMPT}\n\n"
        "Return only JSON with keys: should_retry, failure_category, summary, next_steps. "
        "failure_category must be one of test_failed, test_timeout, dependency_missing, "
        "patch_apply_failed, context_missing, model_format_error, unknown."
    )


def _reflector_user_prompt(
    *,
    latest_result: dict[str, Any],
    diff: str,
    plan: str,
    retry_count: int,
    max_retries: int,
) -> str:
    return "\n\n".join(
        [
            f"# Retry\n{retry_count} / {max_retries}",
            f"# Plan\n{plan}",
            f"# Current Diff\n{diff or '(none)'}",
            f"# Latest Test Result\n{json.dumps(latest_result, ensure_ascii=False, indent=2)}",
        ]
    )


def _next_steps_for_category(category: str) -> list[str]:
    if category == "dependency_missing":
        return ["Check whether the test environment has required dependencies before retrying."]
    if category == "test_timeout":
        return ["Narrow the verification command or inspect possible hangs before retrying."]
    if category == "context_missing":
        return ["Expand selected context to include the missing file or module."]
    if category == "patch_apply_failed":
        return ["Regenerate the patch against the current working tree."]
    if category == "test_failed":
        return ["Inspect the failing assertion and update the patch with a narrower fix."]
    return ["Inspect verification output and decide whether more context is needed."]
