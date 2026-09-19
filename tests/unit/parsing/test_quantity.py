"""Tests del parser de cantidad."""

from __future__ import annotations

from extractor.domain.issues import IssueCode
from extractor.domain.parsing.quantity import parse_quantity
from extractor.domain.profile import QuantityConfig


def test_parse_quantity_empty_is_none_not_zero() -> None:
    value, issues = parse_quantity("")
    assert value is None
    assert value != 0
    assert issues == []


def test_parse_quantity_empty_zero_when_configured() -> None:
    value, issues = parse_quantity("", QuantityConfig(empty_means="zero"))
    assert value == 0
    assert issues == []


def test_parse_quantity_number() -> None:
    value, issues = parse_quantity("12")
    assert value == 12
    assert issues == []


def test_parse_quantity_thousands() -> None:
    value, _issues = parse_quantity("1,250")
    assert value == 1250


def test_parse_quantity_dash() -> None:
    value, issues = parse_quantity("-")
    assert value is None
    assert issues[0].code == IssueCode.QUANTITY_UNPARSEABLE


def test_parse_quantity_na() -> None:
    value, issues = parse_quantity("N/A")
    assert value is None
    assert issues[0].code == IssueCode.QUANTITY_UNPARSEABLE


def test_parse_quantity_negative() -> None:
    value, issues = parse_quantity("-3")
    assert value is None
    assert issues[0].code == IssueCode.QUANTITY_UNPARSEABLE


def test_parse_quantity_on_non_numeric_null() -> None:
    value, issues = parse_quantity("call", QuantityConfig(on_non_numeric="null"))
    assert value is None
    assert issues == []
