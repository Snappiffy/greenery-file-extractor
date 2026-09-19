"""Paquete de dominio puro."""

from extractor.domain.errors import ExtractorError, InvalidProfileError
from extractor.domain.issues import Issue, IssueCode, Severity, make_issue
from extractor.domain.models import (
    BBox,
    Cell,
    Diagnostics,
    Line,
    ParsedRow,
    Row,
    Size,
    Word,
)
from extractor.domain.profile import Profile

__all__ = [
    "BBox",
    "Cell",
    "Diagnostics",
    "ExtractorError",
    "InvalidProfileError",
    "Issue",
    "IssueCode",
    "Line",
    "ParsedRow",
    "Profile",
    "Row",
    "Severity",
    "Size",
    "Word",
    "make_issue",
]
