"""Tests de issues y modelos básicos."""

from __future__ import annotations

from extractor.domain.issues import SEVERITY_BY_CODE, IssueCode, Severity, make_issue
from extractor.domain.models import Diagnostics, Word


def test_all_issue_codes_have_severity() -> None:
    assert set(SEVERITY_BY_CODE) == set(IssueCode)


def test_make_issue_uses_canonical_severity() -> None:
    issue = make_issue(IssueCode.PRICE_UNPARSEABLE, field="price")
    assert issue.severity == Severity.ERROR
    assert SEVERITY_BY_CODE[IssueCode.PRICE_UNPARSEABLE] == Severity.ERROR


def test_word_and_diagnostics_construct() -> None:
    word = Word(text="Ficus", x0=1.0, top=2.0, x1=3.0, bottom=4.0)
    assert word.text == "Ficus"
    diag = Diagnostics(rows_extracted=1)
    assert diag.rows_extracted == 1
