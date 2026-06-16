from __future__ import annotations

from src.slug import normalize_slug


def test_normalize_slug_collapses_duplicate_separators():
    assert normalize_slug("Hello  World!") == "hello-world"


def test_normalize_slug_keeps_existing_lowercase_input():
    assert normalize_slug("already-clean") == "already-clean"
