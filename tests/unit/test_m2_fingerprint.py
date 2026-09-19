"""Tests de aceptación M2: fingerprint y lectura PDF."""

from __future__ import annotations

from pathlib import Path

import pytest
from tests.fixtures.m2 import _generate as gen

from extractor.adapters.readers.pymupdf_reader import PyMuPdfReader
from extractor.domain.errors import DocumentUnreadableError
from extractor.domain.fingerprint import (
    FingerprintComponents,
    compare_components,
    compute_fingerprint,
)
from extractor.domain.layout import is_scanned, text_density
from extractor.engine.lines import group_words_into_lines

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "m2"
HEADER_ANCHOR = "BOTANICAL NAME"


@pytest.fixture(scope="session", autouse=True)
def _ensure_m2_fixtures() -> None:
    gen.main()


def _fingerprint_for(path: Path) -> tuple[str, FingerprintComponents]:
    data = path.read_bytes()
    pages = PyMuPdfReader().read(data)
    page = pages[0]
    lines = group_words_into_lines(page.words, page=page.number)
    result = compute_fingerprint(page, lines, header_anchor_text=HEADER_ANCHOR)
    return result.fingerprint, result.components


def test_fingerprint_identical_across_10_runs() -> None:
    path = FIXTURES / "layout_base.pdf"
    fingerprints = [_fingerprint_for(path)[0] for _ in range(10)]
    assert len(set(fingerprints)) == 1


def test_same_layout_different_prices_and_dates_same_fingerprint() -> None:
    base_fp, base_components = _fingerprint_for(FIXTURES / "layout_base.pdf")
    alt_fp, alt_components = _fingerprint_for(FIXTURES / "layout_alt_prices.pdf")
    assert base_fp == alt_fp
    assert compare_components(base_components, alt_components) == []


def test_shifted_column_changes_boundaries() -> None:
    _base_fp, base_components = _fingerprint_for(FIXTURES / "layout_base.pdf")
    shifted_fp, shifted_components = _fingerprint_for(FIXTURES / "layout_shifted_price.pdf")
    assert _base_fp != shifted_fp
    changed = compare_components(base_components, shifted_components)
    assert "boundaries" in changed
    assert changed == ["boundaries"]


def test_encrypted_pdf_without_password_is_document_unreadable() -> None:
    data = (FIXTURES / "layout_encrypted.pdf").read_bytes()
    with pytest.raises(DocumentUnreadableError) as exc_info:
        PyMuPdfReader().read(data)
    assert exc_info.value.code == "DOCUMENT_UNREADABLE"
    assert exc_info.value.detail.get("reason") == "encrypted"


def test_encrypted_pdf_with_password_opens() -> None:
    data = (FIXTURES / "layout_encrypted.pdf").read_bytes()
    pages = PyMuPdfReader().read(data, password="secret")
    assert len(pages) == 1
    assert pages[0].words


def test_text_density_and_is_scanned_on_native_pdf() -> None:
    pages = PyMuPdfReader().read((FIXTURES / "layout_base.pdf").read_bytes())
    density = text_density(pages)
    assert density > 0
    assert is_scanned(pages) is False


def test_reader_rejects_empty_bytes() -> None:
    with pytest.raises(DocumentUnreadableError):
        PyMuPdfReader().read(b"")
