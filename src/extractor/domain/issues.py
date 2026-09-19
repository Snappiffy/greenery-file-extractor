"""Catálogo de issues y constructores."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict


class Severity(StrEnum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class IssueCode(StrEnum):
    REQUIRED_COLUMN_EMPTY = "REQUIRED_COLUMN_EMPTY"
    ROW_COLUMN_COUNT_MISMATCH = "ROW_COLUMN_COUNT_MISMATCH"
    LINE_PATTERN_NO_MATCH = "LINE_PATTERN_NO_MATCH"
    PRICE_UNPARSEABLE = "PRICE_UNPARSEABLE"
    PRICE_NEGATIVE = "PRICE_NEGATIVE"
    PRICE_IMPLAUSIBLE = "PRICE_IMPLAUSIBLE"
    PRICE_RANGE = "PRICE_RANGE"
    SIZE_UNRECOGNIZED = "SIZE_UNRECOGNIZED"
    SIZE_AMBIGUOUS = "SIZE_AMBIGUOUS"
    SIZE_RECOVERED_FROM_NAME = "SIZE_RECOVERED_FROM_NAME"
    QUANTITY_UNPARSEABLE = "QUANTITY_UNPARSEABLE"
    AVAILABILITY_UNKNOWN_TOKEN = "AVAILABILITY_UNKNOWN_TOKEN"
    AVAILABILITY_EMPTY_DEFAULTED = "AVAILABILITY_EMPTY_DEFAULTED"
    TEXT_CROSSES_BOUNDARY = "TEXT_CROSSES_BOUNDARY"
    MULTILINE_JOINED = "MULTILINE_JOINED"
    OCR_LOW_CONFIDENCE = "OCR_LOW_CONFIDENCE"
    ROW_LIKELY_HEADER = "ROW_LIKELY_HEADER"
    ROW_LIKELY_TOTAL = "ROW_LIKELY_TOTAL"


SEVERITY_BY_CODE: dict[IssueCode, Severity] = {
    IssueCode.REQUIRED_COLUMN_EMPTY: Severity.ERROR,
    IssueCode.ROW_COLUMN_COUNT_MISMATCH: Severity.ERROR,
    IssueCode.LINE_PATTERN_NO_MATCH: Severity.ERROR,
    IssueCode.PRICE_UNPARSEABLE: Severity.ERROR,
    IssueCode.PRICE_NEGATIVE: Severity.ERROR,
    IssueCode.PRICE_IMPLAUSIBLE: Severity.WARNING,
    IssueCode.PRICE_RANGE: Severity.WARNING,
    IssueCode.SIZE_UNRECOGNIZED: Severity.ERROR,
    IssueCode.SIZE_AMBIGUOUS: Severity.ERROR,
    IssueCode.SIZE_RECOVERED_FROM_NAME: Severity.WARNING,
    IssueCode.QUANTITY_UNPARSEABLE: Severity.WARNING,
    IssueCode.AVAILABILITY_UNKNOWN_TOKEN: Severity.WARNING,
    IssueCode.AVAILABILITY_EMPTY_DEFAULTED: Severity.INFO,
    IssueCode.TEXT_CROSSES_BOUNDARY: Severity.WARNING,
    IssueCode.MULTILINE_JOINED: Severity.INFO,
    IssueCode.OCR_LOW_CONFIDENCE: Severity.WARNING,
    IssueCode.ROW_LIKELY_HEADER: Severity.INFO,
    IssueCode.ROW_LIKELY_TOTAL: Severity.INFO,
}


class Issue(BaseModel):
    """Incidencia detectada en una fila o en el documento."""

    model_config = ConfigDict(frozen=True)

    code: IssueCode
    severity: Severity
    field: str | None = None
    detail: str | dict[str, Any] | None = None


def make_issue(
    code: IssueCode,
    *,
    field: str | None = None,
    detail: str | dict[str, Any] | None = None,
) -> Issue:
    """Construye un issue con la severidad canónica del código."""
    return Issue(
        code=code,
        severity=SEVERITY_BY_CODE[code],
        field=field,
        detail=detail,
    )
