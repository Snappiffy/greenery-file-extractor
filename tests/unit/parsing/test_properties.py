"""Property tests de los parsers con hypothesis."""

from __future__ import annotations

from decimal import Decimal

from hypothesis import given
from hypothesis import strategies as st

from extractor.domain.parsing.availability import parse_availability
from extractor.domain.parsing.price import parse_price
from extractor.domain.parsing.quantity import parse_quantity
from extractor.domain.parsing.size import parse_size
from extractor.domain.parsing.text import normalize_text
from extractor.domain.profile import PriceConfig, TextConfig


@given(st.text())
def test_parse_price_never_raises(text: str) -> None:
    value, issues = parse_price(text)
    assert value is None or isinstance(value, Decimal)
    assert isinstance(issues, list)


@given(st.text())
def test_parse_quantity_never_raises(text: str) -> None:
    value, issues = parse_quantity(text)
    assert value is None or isinstance(value, int)
    assert isinstance(issues, list)


@given(st.text())
def test_parse_availability_never_raises(text: str) -> None:
    value, issues = parse_availability(text)
    assert value is None or isinstance(value, bool)
    assert isinstance(issues, list)


@given(st.text(), st.text())
def test_parse_size_never_raises(text: str, plant_name: str) -> None:
    value, issues = parse_size(text, plant_name=plant_name)
    assert value is None or value.magnitude > 0
    assert isinstance(issues, list)


@given(st.text())
def test_normalize_never_raises_and_idempotent(text: str) -> None:
    cfg = TextConfig()
    once = normalize_text(text, cfg)
    twice = normalize_text(once, cfg)
    assert once == twice


@given(
    st.decimals(
        min_value=Decimal("0.01"),
        max_value=Decimal("9999.99"),
        places=2,
        allow_nan=False,
        allow_infinity=False,
    )
)
def test_parse_price_roundtrip_plain(value: Decimal) -> None:
    text = format(value, "f")
    parsed, issues = parse_price(text, PriceConfig())
    assert issues == []
    assert parsed == value.quantize(Decimal("0.01"))


@given(st.text())
def test_parse_quantity_empty_never_zero_by_default(text: str) -> None:
    if text.strip() != "":
        return
    value, _issues = parse_quantity(text)
    assert value is None
