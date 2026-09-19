"""Paquete de dominio puro."""

from extractor.domain.errors import DocumentUnreadableError, ExtractorError, InvalidProfileError
from extractor.domain.fingerprint import FingerprintResult, compute_fingerprint
from extractor.domain.issues import Issue, IssueCode, Severity, make_issue
from extractor.domain.models import (
    BBox,
    Cell,
    Diagnostics,
    Line,
    Page,
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
    "DocumentUnreadableError",
    "ExtractorError",
    "FingerprintResult",
    "InvalidProfileError",
    "Issue",
    "IssueCode",
    "Line",
    "Page",
    "ParsedRow",
    "Profile",
    "Row",
    "Severity",
    "Size",
    "Word",
    "compute_fingerprint",
    "make_issue",
]
