"""Tests del parser de tamaño."""

from __future__ import annotations

from decimal import Decimal

from extractor.domain.issues import IssueCode
from extractor.domain.parsing.size import parse_size
from extractor.domain.profile import SizeConfig, SizePattern


def test_parse_size_inches() -> None:
    value, issues = parse_size('10"')
    assert value is not None
    assert value.magnitude == Decimal("10")
    assert value.unit == "in"
    assert value.dimension == "pot_diameter"
    assert issues == []


def test_parse_size_gallon() -> None:
    value, _issues = parse_size("#5")
    assert value is not None
    assert value.dimension == "pot_volume"
    assert value.magnitude == Decimal("5")


def test_parse_size_recovered_from_name() -> None:
    value, issues = parse_size("", plant_name='Ficus lyrata 10"')
    assert value is not None
    assert value.magnitude == Decimal("10")
    assert any(issue.code == IssueCode.SIZE_RECOVERED_FROM_NAME for issue in issues)


def test_parse_size_unrecognized() -> None:
    value, issues = parse_size("huge")
    assert value is None
    assert issues[0].code == IssueCode.SIZE_UNRECOGNIZED


def test_parse_size_ambiguous() -> None:
    cfg = SizeConfig(
        patterns=[
            SizePattern(regex=r"(?P<v>\d+)\"", unit="in", dimension="pot_diameter"),
            SizePattern(regex=r"(?P<v>\d+)\"", unit="in", dimension="plant_height"),
        ]
    )
    value, issues = parse_size('10"', cfg)
    assert value is None
    assert issues[0].code == IssueCode.SIZE_AMBIGUOUS
    assert "readings" in issues[0].detail  # type: ignore[operator]


def test_parse_size_multiple_same_dimension_takes_first() -> None:
    cfg = SizeConfig(
        patterns=[
            SizePattern(regex=r"(?P<v>\d+)\"", unit="in", dimension="pot_diameter"),
            SizePattern(regex=r"(?P<v>\d+)\s*in", unit="in", dimension="pot_diameter"),
        ]
    )
    value, issues = parse_size('10"', cfg)
    assert value is not None
    assert issues == []
