"""Tests del parser de disponibilidad."""

from __future__ import annotations

from extractor.domain.issues import IssueCode
from extractor.domain.parsing.availability import parse_availability
from extractor.domain.profile import AvailabilityConfig


def test_parse_availability_true() -> None:
    value, issues = parse_availability("yes")
    assert value is True
    assert issues == []


def test_parse_availability_false() -> None:
    value, issues = parse_availability("sold out")
    assert value is False
    assert issues == []


def test_parse_availability_empty_defaulted() -> None:
    value, issues = parse_availability("")
    assert value is True
    assert issues[0].code == IssueCode.AVAILABILITY_EMPTY_DEFAULTED


def test_parse_availability_unknown_token() -> None:
    value, issues = parse_availability("maybe")
    assert value is None
    assert issues[0].code == IssueCode.AVAILABILITY_UNKNOWN_TOKEN


def test_parse_availability_exact_match_not_contains() -> None:
    value, issues = parse_availability("no stock")
    assert value is None
    assert issues[0].code == IssueCode.AVAILABILITY_UNKNOWN_TOKEN


def test_derive_from_quantity() -> None:
    cfg = AvailabilityConfig(derive_from_quantity=True)
    value, issues = parse_availability(
        "",
        cfg,
        quantity=3,
        has_availability_column=False,
    )
    assert value is True
    assert issues == []


def test_derive_from_quantity_zero() -> None:
    cfg = AvailabilityConfig(derive_from_quantity=True)
    value, _issues = parse_availability(
        "",
        cfg,
        quantity=0,
        has_availability_column=False,
    )
    assert value is False
