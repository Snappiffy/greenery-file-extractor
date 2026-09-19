"""Tests de Settings."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from extractor.config import Settings


def test_settings_splits_allowed_hosts() -> None:
    settings = Settings(
        extractor_shared_secret="x" * 32,
        fetch_allowed_hosts="a.example.com, b.example.com",
    )
    assert settings.fetch_allowed_hosts == ["a.example.com", "b.example.com"]


def test_secret_must_be_at_least_32_chars() -> None:
    with pytest.raises(ValidationError):
        Settings(
            extractor_shared_secret="too-short",
            fetch_allowed_hosts=["fixtures.local"],
        )
