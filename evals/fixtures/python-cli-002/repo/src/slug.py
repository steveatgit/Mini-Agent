"""Slug helpers for maintainer evals."""

from __future__ import annotations


def normalize_slug(text: str) -> str:
    return text.strip().lower().replace(" ", "-")
