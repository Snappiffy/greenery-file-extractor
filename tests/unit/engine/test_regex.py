"""Tests unitarios de la estrategia regex."""

from __future__ import annotations

from extractor.domain.issues import IssueCode
from extractor.domain.models import Line, Word
from extractor.domain.profile import Profile
from extractor.engine.strategies.regex import RegexStrategy


def _line(text: str) -> Line:
    x = 52.0
    words = []
    for token in text.split():
        width = 6.0 * len(token)
        words.append(Word(text=token, x0=x, top=120, x1=x + width, bottom=132))
        x += width + 4.0
    return Line(
        words=words,
        top=120,
        x0=52,
        x1=x,
        bottom=132,
        page=1,
        line_index=0,
    )


def test_regex_cut_named_groups() -> None:
    profile = Profile.from_payload(
        {
            "schema_version": 1,
            "version": 1,
            "document": {"kind": "pdf", "pages": "all"},
            "table": {
                "strategy": "regex",
                "line_pattern": (
                    r"^(?P<grower_code>[A-Z]{3}-\d{4})\s+"
                    r"(?P<plant_name>.+?)\s+"
                    r"(?P<size>\d+\"?)\s+"
                    r"\$(?P<price>[\d.]+)\s+"
                    r"(?P<quantity>\d+)$"
                ),
                "multiline": {"enabled": False},
            },
            "columns": [
                {"role": "grower_code", "index": 0},
                {"role": "plant_name", "index": 1, "required": True},
                {"role": "size", "index": 2, "required": True},
                {"role": "price", "index": 3},
                {"role": "quantity", "index": 4},
            ],
        }
    )
    cells, issues = RegexStrategy().cut([_line('ACM-0001 Ficus lyrata 10" $42.50 12')], profile)[0]
    by_role = {cell.role: cell.raw for cell in cells}
    assert by_role["grower_code"] == "ACM-0001"
    assert by_role["plant_name"] == "Ficus lyrata"
    assert by_role["size"] == '10"'
    assert by_role["price"] == "42.50"
    assert by_role["quantity"] == "12"
    assert issues == []


def test_regex_no_match_emits_issue() -> None:
    profile = Profile.from_payload(
        {
            "schema_version": 1,
            "version": 1,
            "document": {"kind": "pdf", "pages": "all"},
            "table": {
                "strategy": "regex",
                "line_pattern": r"^(?P<plant_name>.+)\s+(?P<size>\d+\")$",
                "multiline": {"enabled": False},
            },
            "columns": [
                {"role": "plant_name", "index": 0, "required": True},
                {"role": "size", "index": 1, "required": True},
            ],
        }
    )
    _cells, issues = RegexStrategy().cut([_line("not a product line")], profile)[0]
    assert any(issue.code == IssueCode.LINE_PATTERN_NO_MATCH for issue in issues)
