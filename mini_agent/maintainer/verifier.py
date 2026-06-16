"""Verification command runner for maintainer workflows."""

from __future__ import annotations

import subprocess
import time
from pathlib import Path
from typing import Any


DANGEROUS_PATTERNS = (
    "rm -rf /",
    "sudo ",
    "chmod -r 777",
    "curl ",
    "| sh",
    "git push",
)


def run_verification(repo_path: Path, command: str | None, timeout: int = 120) -> dict[str, Any]:
    if not command:
        return {
            "command": None,
            "exit_code": None,
            "stdout": "",
            "stderr": "",
            "duration_seconds": 0.0,
            "status": "skipped",
            "summary": "No test command was provided or detected.",
        }
    _validate_command(command)
    start = time.monotonic()
    try:
        result = subprocess.run(command, cwd=repo_path, shell=True, capture_output=True, text=True, timeout=timeout)
        duration = time.monotonic() - start
        status = "pass" if result.returncode == 0 else "fail"
        return {
            "command": command,
            "exit_code": result.returncode,
            "stdout": _truncate(result.stdout),
            "stderr": _truncate(result.stderr),
            "duration_seconds": round(duration, 3),
            "status": status,
            "summary": summarize_result(status, result.stdout, result.stderr, result.returncode),
        }
    except subprocess.TimeoutExpired as exc:
        duration = time.monotonic() - start
        return {
            "command": command,
            "exit_code": None,
            "stdout": _truncate(exc.stdout or ""),
            "stderr": _truncate(exc.stderr or ""),
            "duration_seconds": round(duration, 3),
            "status": "timeout",
            "summary": f"Verification timed out after {timeout} seconds.",
        }


def render_test_results(results: list[dict[str, Any]]) -> str:
    lines = ["# Test Results", ""]
    for index, result in enumerate(results, 1):
        lines.extend(
            [
                f"## Run {index}",
                "",
                f"- command: `{result.get('command') or 'none'}`",
                f"- status: {result.get('status')}",
                f"- exit_code: {result.get('exit_code')}",
                f"- duration_seconds: {result.get('duration_seconds')}",
                f"- summary: {result.get('summary')}",
                "",
                "### stdout",
                "```text",
                result.get("stdout", "") or "(empty)",
                "```",
                "",
                "### stderr",
                "```text",
                result.get("stderr", "") or "(empty)",
                "```",
                "",
            ]
        )
    return "\n".join(lines)


def summarize_result(status: str, stdout: str, stderr: str, exit_code: int) -> str:
    if status == "pass":
        return "Verification command completed successfully."
    combined = "\n".join(part for part in [stderr, stdout] if part)
    tail = "\n".join(combined.splitlines()[-20:])
    if not tail:
        tail = f"Command failed with exit code {exit_code} and no output."
    return _truncate(tail, limit=2000)


def _validate_command(command: str) -> None:
    lowered = command.lower()
    for pattern in DANGEROUS_PATTERNS:
        if pattern in lowered:
            raise ValueError(f"Refusing to run verification command containing dangerous pattern: {pattern}")


def _truncate(value: str | bytes, limit: int = 12000) -> str:
    if isinstance(value, bytes):
        text = value.decode("utf-8", errors="replace")
    else:
        text = value
    if len(text) <= limit:
        return text
    return text[:limit] + "\n...[truncated]"
