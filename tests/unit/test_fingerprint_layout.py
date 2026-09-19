"""Tests del fingerprint y layout puros."""

from __future__ import annotations

from extractor.domain.fingerprint import (
    FingerprintComponents,
    compare_components,
    hash_components,
    normalize_header_text,
)
from extractor.domain.layout import ColumnCandidate, find_column_candidates
from extractor.domain.models import Word


def test_normalize_header_strips_digits_and_year() -> None:
    a = normalize_header_text("ACME NURSERY — SPRING 2026")
    b = normalize_header_text("ACME NURSERY — SPRING 2027")
    assert a == b
    assert "2026" not in a
    assert a == "acme nursery spring"


def test_compare_components_reports_boundaries() -> None:
    left = FingerprintComponents(
        page_size="612x792",
        rotation="0",
        column_count="4",
        boundaries="50,270,370,470",
        header_text="botanical name",
        strategy="columns",
    )
    right = left.model_copy(update={"boundaries": "50,270,400,470"})
    assert compare_components(left, right) == ["boundaries"]
    assert hash_components(left) != hash_components(right)


def test_column_candidates_histogram() -> None:
    words: list[Word] = []
    for row in range(10):
        top = 140.0 + row * 16
        words.extend(
            [
                Word(text=f"Plant{row}", x0=52.0, top=top, x1=100.0, bottom=top + 10),
                Word(text='10"', x0=268.0, top=top, x1=290.0, bottom=top + 10),
                Word(text="$1.00", x0=372.0, top=top, x1=400.0, bottom=top + 10),
            ]
        )
    candidates = find_column_candidates(words, line_count=10)
    xs = [c.x for c in candidates]
    assert 52.0 in xs or any(abs(x - 52.0) < 1 for x in xs)
    assert any(abs(x - 268.0) < 1 for x in xs)
    assert any(abs(x - 372.0) < 1 for x in xs)
    assert all(isinstance(c, ColumnCandidate) for c in candidates)
