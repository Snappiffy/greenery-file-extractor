"""Tests de normalización de texto."""

from __future__ import annotations

from extractor.domain.parsing.text import normalize_text
from extractor.domain.profile import TextConfig


def test_normalize_collapses_whitespace() -> None:
    assert normalize_text("Ficus  lyrata\t'Bambino'") == "Ficus lyrata 'Bambino'"


def test_normalize_drops_soft_hyphen() -> None:
    assert normalize_text("dra\u00adcena") == "dracena"


def test_normalize_idempotent() -> None:
    cfg = TextConfig()
    once = normalize_text("  A\u00ad  B  ", cfg)
    twice = normalize_text(once, cfg)
    assert once == twice
