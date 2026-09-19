"""Tests adicionales para cobertura del dominio."""

from __future__ import annotations

from decimal import Decimal

import pytest
from tests.helpers import minimal_profile

from extractor.domain.errors import InvalidProfileError
from extractor.domain.issues import IssueCode
from extractor.domain.models import Line, Size, Word
from extractor.domain.parsing.availability import parse_availability
from extractor.domain.parsing.price import parse_price
from extractor.domain.parsing.quantity import parse_quantity
from extractor.domain.parsing.size import parse_size
from extractor.domain.parsing.text import normalize_text
from extractor.domain.profile import (
    AvailabilityConfig,
    PriceConfig,
    Profile,
    SizeConfig,
    SizePattern,
    TextConfig,
)


def test_line_text_and_size_serializable() -> None:
    word = Word(text="A", x0=0, top=1, x1=2, bottom=3)
    line = Line(words=[word], top=1, x0=0, x1=2, bottom=3, page=1, line_index=0)
    assert line.text == "A"
    size = Size(magnitude=Decimal("10.0"), unit="in", dimension="pot_diameter", raw='10"')
    assert size.to_serializable()["magnitude"] == "10.0"


def test_availability_empty_means_false_and_unknown() -> None:
    value, issues = parse_availability("", AvailabilityConfig(empty_means="false"))
    assert value is False
    assert issues[0].code == IssueCode.AVAILABILITY_EMPTY_DEFAULTED

    value, issues = parse_availability("", AvailabilityConfig(empty_means="unknown"))
    assert value is None

    value, issues = parse_availability(
        "x",
        AvailabilityConfig(derive_from_quantity=False),
        has_availability_column=False,
    )
    assert value is None
    assert issues == []


def test_price_empty_after_strip_and_custom_separators() -> None:
    value, issues = parse_price("$", PriceConfig(empty_means="zero"))
    assert value == Decimal("0.00")

    value, issues = parse_price(
        "1.250,50",
        PriceConfig(decimal_separator=",", thousands_separator="."),
    )
    assert value == Decimal("1250.50")
    assert issues == []


def test_price_unparseable_range() -> None:
    value, issues = parse_price("12.00 - ask")
    assert value is None
    assert any(i.code == IssueCode.PRICE_UNPARSEABLE for i in issues)


def test_price_range_max() -> None:
    value, issues = parse_price("40.00 - 55.00", PriceConfig(on_range="max"))
    assert value == Decimal("55.00")
    assert any(i.code == IssueCode.PRICE_RANGE for i in issues)


def test_quantity_plus_and_garbage() -> None:
    value, issues = parse_quantity("+7")
    assert value == 7
    assert issues == []

    value, issues = parse_quantity("12.5")
    assert value is None
    assert issues[0].code == IssueCode.QUANTITY_UNPARSEABLE


def test_size_on_no_match_null_and_first() -> None:
    null_cfg = SizeConfig(on_no_match="null")
    value, issues = parse_size("nope", null_cfg)
    assert value is None
    assert issues == []

    first_cfg = SizeConfig(
        patterns=[
            SizePattern(regex=r"(?P<v>\d+)\"", unit="in", dimension="pot_diameter"),
            SizePattern(regex=r"(?P<v>\d+)\"", unit="in", dimension="plant_height"),
        ],
        on_multiple_matches="first",
    )
    value, issues = parse_size('10"', first_cfg)
    assert value is not None
    assert value.dimension == "pot_diameter"
    assert issues == []


def test_size_skips_non_positive_and_bad_group() -> None:
    cfg = SizeConfig(
        patterns=[
            SizePattern(regex=r"(?P<v>0+)\"", unit="in", dimension="pot_diameter"),
            SizePattern(regex=r"(?P<v>\d+)\"", unit="in", dimension="pot_diameter"),
        ]
    )
    value, _issues = parse_size('10"', cfg)
    assert value is not None
    assert value.magnitude == Decimal("10")


def test_normalize_with_flags_off() -> None:
    cfg = TextConfig(
        collapse_whitespace=False,
        trim=False,
        drop_soft_hyphens=False,
    )
    assert normalize_text("  a\u00ad  b  ", cfg) == "  a\u00ad  b  "


def test_profile_ruling_defaults_and_header_regex() -> None:
    payload = minimal_profile(
        table={
            "strategy": "ruling",
            "header_anchor": {
                "text": r"^Item$",
                "match": "regex",
                "on_every_page": True,
                "offset_lines": 0,
            },
            "stop_patterns": [],
        },
        columns=[
            {"role": "plant_name", "index": 0, "required": True},
            {"role": "size", "index": 1, "required": True},
        ],
    )
    profile = Profile.from_payload(payload)
    assert profile.table.ruling is not None
    assert profile.table.header_anchor is not None


def test_profile_missing_boundaries() -> None:
    payload = minimal_profile()
    payload["table"]["column_boundaries"] = None
    with pytest.raises(InvalidProfileError):
        Profile.from_payload(payload)


def test_profile_regex_missing_pattern() -> None:
    payload = minimal_profile(
        table={"strategy": "regex", "stop_patterns": []},
        columns=[
            {"role": "plant_name", "index": 0, "required": True},
            {"role": "size", "index": 1, "required": True},
        ],
    )
    with pytest.raises(InvalidProfileError, match="line_pattern"):
        Profile.from_payload(payload)


def test_profile_invalid_max_reasonable() -> None:
    payload = minimal_profile()
    payload["parsing"] = {"price": {"max_reasonable": "not-a-number"}}
    with pytest.raises(InvalidProfileError):
        Profile.from_payload(payload)


def test_profile_skip_pages_bad_regex() -> None:
    payload = minimal_profile()
    payload["document"] = {
        "kind": "pdf",
        "pages": "all",
        "skip_pages_matching": ["[unterminated"],
    }
    with pytest.raises(InvalidProfileError):
        Profile.from_payload(payload)


def test_profile_drop_rows_bad_regex() -> None:
    payload = minimal_profile()
    payload["filters"] = {"drop_rows_matching": {"plant_name": ["[bad"]}}
    with pytest.raises(InvalidProfileError):
        Profile.from_payload(payload)


def test_profile_from_payload_schema_error() -> None:
    with pytest.raises(InvalidProfileError):
        Profile.from_payload({"columns": "not-a-list"})
