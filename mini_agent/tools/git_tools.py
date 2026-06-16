"""Git tools for repository maintenance workflows."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from .base import Tool, ToolResult


class _GitTool(Tool):
    def __init__(self, repo_path: str = "."):
        self.repo_path = Path(repo_path).expanduser().resolve()

    def _git(self, args: list[str]) -> ToolResult:
        result = subprocess.run(["git", "-C", str(self.repo_path), *args], capture_output=True, text=True)
        if result.returncode != 0:
            return ToolResult(success=False, content=result.stdout, error=result.stderr.strip())
        return ToolResult(success=True, content=result.stdout.strip())


class GitStatusTool(_GitTool):
    @property
    def name(self) -> str:
        return "git_status"

    @property
    def description(self) -> str:
        return "Show concise git status for the maintainer repository."

    @property
    def parameters(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}}

    async def execute(self) -> ToolResult:
        return self._git(["status", "--short"])


class GitDiffTool(_GitTool):
    @property
    def name(self) -> str:
        return "git_diff"

    @property
    def description(self) -> str:
        return "Show the current working tree diff for the maintainer repository."

    @property
    def parameters(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}}

    async def execute(self) -> ToolResult:
        return self._git(["diff", "--binary"])


class GitCreatePatchTool(_GitTool):
    @property
    def name(self) -> str:
        return "git_create_patch"

    @property
    def description(self) -> str:
        return "Create a patch from the current working tree diff."

    @property
    def parameters(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}}

    async def execute(self) -> ToolResult:
        return self._git(["diff", "--binary", "--patch"])


class GitApplyPatchTool(_GitTool):
    @property
    def name(self) -> str:
        return "git_apply_patch"

    @property
    def description(self) -> str:
        return "Apply a patch file inside the maintainer repository."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {"patch_path": {"type": "string", "description": "Patch file path"}},
            "required": ["patch_path"],
        }

    async def execute(self, patch_path: str) -> ToolResult:
        path = Path(patch_path).expanduser()
        if not path.is_absolute():
            path = self.repo_path / path
        result = subprocess.run(["git", "-C", str(self.repo_path), "apply", str(path)], capture_output=True, text=True)
        if result.returncode != 0:
            return ToolResult(success=False, content=result.stdout, error=result.stderr.strip())
        return ToolResult(success=True, content=result.stdout.strip() or f"Applied patch: {path}")


class GitRestoreRunChangesTool(_GitTool):
    @property
    def name(self) -> str:
        return "git_restore_run_changes"

    @property
    def description(self) -> str:
        return "Restore tracked working tree changes for specific paths. Does not delete untracked files."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "paths": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Tracked paths to restore",
                }
            },
            "required": ["paths"],
        }

    async def execute(self, paths: list[str]) -> ToolResult:
        if not paths:
            return ToolResult(success=False, content="", error="paths must not be empty")
        return self._git(["restore", "--", *paths])


def create_git_tools(repo_path: str = ".") -> list[Tool]:
    return [
        GitStatusTool(repo_path),
        GitDiffTool(repo_path),
        GitApplyPatchTool(repo_path),
        GitCreatePatchTool(repo_path),
        GitRestoreRunChangesTool(repo_path),
    ]
