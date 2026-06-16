from __future__ import annotations

from pathlib import Path


def test_readme_mentions_maintainer_workflow():
    content = Path("README.md").read_text(encoding="utf-8")
    assert "mini-agent maintain" in content
    assert "artifacts" in content
