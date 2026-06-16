from __future__ import annotations

import pytest

from src.demo_cli import greet


def test_greet_accepts_valid_name():
    assert greet("Mini-Agent") == "Hello, Mini-Agent!"


def test_greet_rejects_empty_name():
    with pytest.raises(ValueError):
        greet("")
