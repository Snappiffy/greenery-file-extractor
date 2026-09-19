"""Tests unitarios de la estrategia columns."""

from __future__ import annotations

from tests.helpers import minimal_profile

from extractor.domain.issues import IssueCode
from extractor.domain.models import Line, Word
from extractor.domain.profile import Profile
from extractor.engine.strategies.columns import ColumnsStrategy


def test_columns_cut_basic() -> None:
    profile = Profile.from_payload(minimal_profile())
    line = Line(
        words=[
            Word(text="Ficus", x0=52, top=140, x1=90, bottom=150),
            Word(text='10"', x0=270, top=140, x1=290, bottom=150),
            Word(text="$1.00", x0=380, top=140, x1=410, bottom=150),
            Word(text="3", x0=480, top=140, x1=490, bottom=150),
        ],
        top=140,
        x0=52,
        x1=480,
        bottom=150,
        page=1,
        line_index=0,
    )
    # boundaries in minimal_profile: [52, 268.5, 372, 468, 540]
    cells, issues = ColumnsStrategy().cut([line], profile)[0]
    by_role = {
        c.role: c.raw for c in cells if c.role in {"plant_name", "size", "price", "quantity"}
    }
    assert by_role["plant_name"] == "Ficus"
    assert by_role["size"] == '10"'
    assert by_role["price"] == "$1.00"
    assert by_role["quantity"] == "3"
    assert issues == []


def test_columns_crosses_boundary() -> None:
    profile = Profile.from_payload(minimal_profile())
    line = Line(
        words=[Word(text="Wide", x0=260, top=140, x1=280, bottom=150)],
        top=140,
        x0=260,
        x1=280,
        bottom=150,
        page=1,
        line_index=0,
    )
    _cells, issues = ColumnsStrategy().cut([line], profile)[0]
    assert any(i.code == IssueCode.TEXT_CROSSES_BOUNDARY for i in issues)
