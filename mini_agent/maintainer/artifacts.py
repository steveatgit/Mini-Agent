"""Artifact writing helpers for maintainer runs."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


_MAX_STATE_STRING = 1200
_MAX_STATE_LIST_ITEMS = 60
_MAX_STATE_DICT_ITEMS = 80


def make_run_id(slug: str | None = None) -> str:
    """Create a timestamped run id."""

    suffix = _slugify(slug or "maintain")
    return f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{suffix}"


def _slugify(value: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in value.strip())
    parts = [part for part in cleaned.split("-") if part]
    return "-".join(parts)[:40] or "maintain"


class ArtifactWriter:
    """Writes run artifacts under artifacts/runs/<run_id>."""

    def __init__(self, base_dir: Path, run_id: str):
        self.run_id = run_id
        self.run_dir = base_dir / "artifacts" / "runs" / run_id
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.trace_path = self.run_dir / "tool_trace.jsonl"

    def write_text(self, filename: str, content: str) -> Path:
        path = self.run_dir / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def write_json(self, filename: str, payload: Any) -> Path:
        return self.write_text(filename, json.dumps(payload, ensure_ascii=False, indent=2))

    def append_trace(self, event: dict[str, Any]) -> None:
        event = {"time": datetime.now().isoformat(timespec="seconds"), **event}
        with self.trace_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")


def summarize_state_for_json(payload: Any) -> Any:
    """Reduce large runtime state to a JSON-safe, compact structure."""

    if payload is None or isinstance(payload, (bool, int, float)):
        return payload
    if isinstance(payload, str):
        return payload if len(payload) <= _MAX_STATE_STRING else payload[:_MAX_STATE_STRING] + "\n...[truncated]"
    if isinstance(payload, Path):
        return str(payload)
    if isinstance(payload, dict):
        items = list(payload.items())
        summarized: dict[str, Any] = {}
        for key, value in items[:_MAX_STATE_DICT_ITEMS]:
            if key == "test_results" and isinstance(value, list):
                summarized[key] = [_summarize_test_result(item) for item in value[:_MAX_STATE_LIST_ITEMS]]
            else:
                summarized[key] = summarize_state_for_json(value)
        if len(items) > _MAX_STATE_DICT_ITEMS:
            summarized["...truncated_keys"] = len(items) - _MAX_STATE_DICT_ITEMS
        return summarized
    if isinstance(payload, list):
        items = [summarize_state_for_json(item) for item in payload[:_MAX_STATE_LIST_ITEMS]]
        if len(payload) > _MAX_STATE_LIST_ITEMS:
            items.append(f"...truncated {len(payload) - _MAX_STATE_LIST_ITEMS} items")
        return items
    if isinstance(payload, tuple):
        return summarize_state_for_json(list(payload))
    return str(payload)


def _summarize_test_result(result: Any) -> Any:
    if not isinstance(result, dict):
        return summarize_state_for_json(result)
    keep = {
        "command",
        "exit_code",
        "status",
        "duration_seconds",
        "summary",
    }
    summarized = {key: summarize_state_for_json(value) for key, value in result.items() if key in keep}
    return summarized
