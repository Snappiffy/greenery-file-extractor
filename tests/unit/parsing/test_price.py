"""Tests del parser de precio."""

from __future__ import annotations

from decimal import Decimal

from extractor.domain.issues import IssueCode
from extractor.domain.parsing.price import parse_price
from extractor.domain.profile import PriceConfig


def test_parse_price_basic() -> None:
    value, issues = parse_price("$42.50")
    assert value == Decimal("42.50")
    assert issues == []


def test_parse_price_never_uses_float() -> None:
    value, _issues = parse_price("0.1")
    assert value is not None
    assert isinstance(value, Decimal)
    assert value + Decimal("0.2") == Decimal("0.3")


def test_parse_price_empty_unknown() -> None:
    value, issues = parse_price("")
    assert value is None
    assert issues == []


def test_parse_price_empty_zero() -> None:
    value, issues = parse_price("", PriceConfig(empty_means="zero"))
    assert value == Decimal("0.00")
    assert issues == []


def test_parse_price_thousands() -> None:
    value, issues = parse_price("$1,250.00")
    assert value == Decimal("1250.00")
    assert issues == []


def test_parse_price_range_min() -> None:
    value, issues = parse_price("40.00 - 55.00")
    assert value == Decimal("40.00")
    assert any(issue.code == IssueCode.PRICE_RANGE for issue in issues)


def test_parse_price_range_issue() -> None:
    value, issues = parse_price("40.00 - 55.00", PriceConfig(on_range="issue"))
    assert value is None
    assert any(issue.code == IssueCode.PRICE_RANGE for issue in issues)


def test_parse_price_unparseable() -> None:
    value, issues = parse_price("ask")
    assert value is None
    assert issues[0].code == IssueCode.PRICE_UNPARSEABLE


def test_parse_price_negative() -> None:
    value, issues = parse_price("-3.00")
    assert value == Decimal("-3.00")
    assert any(issue.code == IssueCode.PRICE_NEGATIVE for issue in issues)


def test_parse_price_implausible() -> None:
    value, issues = parse_price("99999.00")
    assert value == Decimal("99999.00")
    assert any(issue.code == IssueCode.PRICE_IMPLAUSIBLE for issue in issues)
