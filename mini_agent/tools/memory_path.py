"""Memory path helpers."""

import hashlib
from pathlib import Path


def get_workspace_id(workspace_dir: str) -> str:
    """Return a stable workspace identifier based on absolute path."""
    workspace_path = str(Path(workspace_dir).expanduser().resolve())
    return hashlib.sha256(workspace_path.encode("utf-8")).hexdigest()[:16]


def get_workspace_memory_file(workspace_dir: str) -> Path:
    """Return the per-workspace JSON memory file path."""
    memory_dir = Path.home() / ".mini-agent" / "memory"
    memory_dir.mkdir(parents=True, exist_ok=True)
    return memory_dir / f"{get_workspace_id(workspace_dir)}.json"
