"""Artifact writing helpers for maintainer runs."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


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
