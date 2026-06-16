"""Repository inspection tools for maintainer workflows."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from mini_agent.maintainer.repo_inspector import detect_test_command, list_repo_files, scan_repo

from .base import Tool, ToolResult


class _RepoTool(Tool):
    def __init__(self, repo_path: str = "."):
        self.repo_path = Path(repo_path).expanduser().resolve()


class RepoTreeTool(_RepoTool):
    @property
    def name(self) -> str:
        return "repo_tree"

    @property
    def description(self) -> str:
        return "List tracked repository files for maintainer context selection."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {"max_files": {"type": "integer", "default": 240}},
        }

    async def execute(self, max_files: int = 240) -> ToolResult:
        files = list_repo_files(self.repo_path, max_files=max_files)
        return ToolResult(success=True, content="\n".join(files))


class RepoGrepTool(_RepoTool):
    @property
    def name(self) -> str:
        return "repo_grep"

    @property
    def description(self) -> str:
        return "Search repository text using git grep."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Search pattern"},
                "max_matches": {"type": "integer", "default": 80},
            },
            "required": ["pattern"],
        }

    async def execute(self, pattern: str, max_matches: int = 80) -> ToolResult:
        result = subprocess.run(
            ["git", "-C", str(self.repo_path), "grep", "-n", "--", pattern],
            capture_output=True,
            text=True,
        )
        if result.returncode not in {0, 1}:
            return ToolResult(success=False, content=result.stdout, error=result.stderr.strip())
        lines = result.stdout.splitlines()[:max_matches]
        return ToolResult(success=True, content="\n".join(lines) if lines else "(no matches)")


class RepoFileSummaryTool(_RepoTool):
    @property
    def name(self) -> str:
        return "repo_file_summary"

    @property
    def description(self) -> str:
        return "Return repository language, key file, and test file summary as JSON."

    @property
    def parameters(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}}

    async def execute(self) -> ToolResult:
        return ToolResult(success=True, content=json.dumps(scan_repo(self.repo_path), ensure_ascii=False, indent=2))


class RepoDetectTestCommandTool(_RepoTool):
    @property
    def name(self) -> str:
        return "repo_detect_test_command"

    @property
    def description(self) -> str:
        return "Infer the smallest likely test command for this repository."

    @property
    def parameters(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}}

    async def execute(self) -> ToolResult:
        files = list_repo_files(self.repo_path)
        command = detect_test_command(self.repo_path, files)
        return ToolResult(success=True, content=command or "")


def create_repo_tools(repo_path: str = ".") -> list[Tool]:
    return [
        RepoTreeTool(repo_path),
        RepoGrepTool(repo_path),
        RepoFileSummaryTool(repo_path),
        RepoDetectTestCommandTool(repo_path),
    ]
