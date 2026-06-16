"""Prompts and validated payloads for maintainer model nodes."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


ISSUE_TRIAGE_PROMPT = """You are triaging a software issue for a local repository maintainer workflow.
Return a compact JSON object with issue_type, summary, keywords, suspected_files, and acceptance_criteria.
Prefer concrete files and observable behavior over broad speculation."""

CONTEXT_SELECT_PROMPT = """Select the smallest useful set of files for fixing the issue.
Use repository metadata, file names, tests, and issue keywords. Return JSON with files and rationale."""

PLAN_PATCH_PROMPT = """Create a patch plan for a maintainer agent.
The plan must include target files, proposed changes, test strategy, and risks."""

FAILURE_REFLECTION_PROMPT = """Analyze a failed verification run.
Use the test output, current diff, and plan to decide whether another implementation attempt is justified."""

PR_WRITER_PROMPT = """Write a concise pull request description with summary, issue context, verification, and risk."""


class IssueTriagePayload(BaseModel):
    """Validated issue triage output."""

    issue_type: str = Field(default="task", max_length=40)
    summary: str = Field(default="", max_length=300)
    keywords: list[str] = Field(default_factory=list, max_length=20)
    suspected_files: list[str] = Field(default_factory=list, max_length=20)
    acceptance_criteria: list[str] = Field(default_factory=list, max_length=12)

    @field_validator("issue_type")
    @classmethod
    def clean_issue_type(cls, value: str) -> str:
        issue_type = str(value).strip().lower()
        if issue_type not in {"bug", "task", "feature", "test", "docs"}:
            return "task"
        return issue_type

    @field_validator("summary")
    @classmethod
    def clean_summary(cls, value: str) -> str:
        return str(value).strip()[:300]

    @field_validator("keywords", "suspected_files", "acceptance_criteria")
    @classmethod
    def clean_list(cls, value: list[str]) -> list[str]:
        cleaned = []
        for item in value:
            text = str(item).strip()
            if text:
                cleaned.append(text[:240])
        return list(dict.fromkeys(cleaned))


class ContextSelectionPayload(BaseModel):
    """Validated context selection output."""

    files: list[str] = Field(default_factory=list, max_length=20)
    rationale: str = Field(default="", max_length=600)

    @field_validator("files")
    @classmethod
    def clean_files(cls, value: list[str]) -> list[str]:
        cleaned = []
        for item in value:
            path = str(item).strip().lstrip("/")
            if path and ".." not in path.split("/"):
                cleaned.append(path[:240])
        return list(dict.fromkeys(cleaned))

    @field_validator("rationale")
    @classmethod
    def clean_rationale(cls, value: str) -> str:
        return str(value).strip()[:600]


class PatchPlanPayload(BaseModel):
    """Validated patch planning output."""

    target_files: list[str] = Field(default_factory=list, max_length=20)
    changes: list[str] = Field(default_factory=list, max_length=20)
    test_strategy: list[str] = Field(default_factory=list, max_length=12)
    risks: list[str] = Field(default_factory=list, max_length=12)

    @field_validator("target_files", "changes", "test_strategy", "risks")
    @classmethod
    def clean_list(cls, value: list[str]) -> list[str]:
        cleaned = []
        for item in value:
            text = str(item).strip()
            if text:
                cleaned.append(text[:300])
        return list(dict.fromkeys(cleaned))


class FailureReflectionPayload(BaseModel):
    """Validated verification failure reflection output."""

    should_retry: bool = False
    failure_category: str = Field(default="unknown", max_length=80)
    summary: str = Field(default="", max_length=800)
    next_steps: list[str] = Field(default_factory=list, max_length=8)

    @field_validator("failure_category", "summary")
    @classmethod
    def clean_string(cls, value: str) -> str:
        return str(value).strip()

    @field_validator("next_steps")
    @classmethod
    def clean_next_steps(cls, value: list[str]) -> list[str]:
        cleaned = []
        for item in value:
            text = str(item).strip()
            if text:
                cleaned.append(text[:300])
        return list(dict.fromkeys(cleaned))
