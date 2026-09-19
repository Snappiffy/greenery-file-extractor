"""Tests del perfil de extracción."""

from __future__ import annotations

import pytest
from tests.helpers import minimal_profile

from extractor.domain.errors import InvalidProfileError
from extractor.domain.profile import Profile


def test_valid_profile_loads() -> None:
    profile = Profile.from_payload(minimal_profile())
    assert profile.table.strategy == "columns"
    assert profile.columns[0].role == "plant_name"


def test_duplicate_role_raises_domain_error() -> None:
    payload = minimal_profile(
        columns=[
            {"role": "plant_name", "index": 0, "required": True},
            {"role": "plant_name", "index": 1, "required": True},
            {"role": "size", "index": 2, "required": True},
        ]
    )
    with pytest.raises(InvalidProfileError) as exc_info:
        Profile.from_payload(payload)
    assert exc_info.value.code == "INVALID_PROFILE"
    assert "plant_name" in exc_info.value.message
    assert "duplicate_roles" in exc_info.value.detail


def test_missing_size_role_raises() -> None:
    payload = minimal_profile(columns=[{"role": "plant_name", "index": 0, "required": True}])
    with pytest.raises(InvalidProfileError):
        Profile.from_payload(payload)


def test_plant_name_must_be_required() -> None:
    payload = minimal_profile(
        columns=[
            {"role": "plant_name", "index": 0, "required": False},
            {"role": "size", "index": 1, "required": True},
        ]
    )
    with pytest.raises(InvalidProfileError, match="plant_name"):
        Profile.from_payload(payload)


def test_column_boundaries_must_be_increasing() -> None:
    payload = minimal_profile()
    payload["table"]["column_boundaries"] = [100.0, 50.0, 200.0]
    with pytest.raises(InvalidProfileError, match="strictly increasing"):
        Profile.from_payload(payload)


def test_column_index_out_of_range() -> None:
    payload = minimal_profile(
        columns=[
            {"role": "plant_name", "index": 0, "required": True},
            {"role": "size", "index": 99, "required": True},
        ]
    )
    with pytest.raises(InvalidProfileError, match="out of range"):
        Profile.from_payload(payload)


def test_invalid_regex_names_where() -> None:
    payload = minimal_profile()
    payload["table"]["stop_patterns"] = ["[invalid"]
    with pytest.raises(InvalidProfileError) as exc_info:
        Profile.from_payload(payload)
    assert "stop_patterns" in str(exc_info.value.detail.get("where", ""))


def test_regex_strategy_requires_named_groups() -> None:
    payload = minimal_profile(
        table={
            "strategy": "regex",
            "line_pattern": r"^(?P<plant_name>.+)$",
            "stop_patterns": [],
        },
        columns=[
            {"role": "plant_name", "index": 0, "required": True},
            {"role": "size", "index": 1, "required": True},
        ],
    )
    with pytest.raises(InvalidProfileError) as exc_info:
        Profile.from_payload(payload)
    assert exc_info.value.detail.get("role") == "size"
