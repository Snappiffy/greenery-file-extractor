"""Parser de disponibilidad."""

from __future__ import annotations

import re
import unicodedata

from extractor.domain.issues import Issue, IssueCode, make_issue
from extractor.domain.profile import AvailabilityConfig

_WHITESPACE_RE = re.compile(r"\s+")


def parse_availability(
    text: str,
    cfg: AvailabilityConfig | None = None,
    *,
    quantity: int | None = None,
    has_availability_column: bool = True,
) -> tuple[bool | None, list[Issue]]:
    """Parsea disponibilidad a bool o None. No lanza excepciones."""
    config = cfg if cfg is not None else AvailabilityConfig()

    if not has_availability_column:
        if config.derive_from_quantity:
            return (quantity is not None and quantity > 0), []
        return None, []

    normalized = _normalize_token(text)
    if normalized == "":
        issues = [
            make_issue(
                IssueCode.AVAILABILITY_EMPTY_DEFAULTED,
                field="availability",
                detail=f"empty column; profile empty_means={config.empty_means}",
            )
        ]
        if config.empty_means == "true":
            return True, issues
        if config.empty_means == "false":
            return False, issues
        return None, issues

    true_values = {_normalize_token(value) for value in config.true_values}
    false_values = {_normalize_token(value) for value in config.false_values}

    if normalized in true_values:
        return True, []
    if normalized in false_values:
        return False, []

    return None, [
        make_issue(
            IssueCode.AVAILABILITY_UNKNOWN_TOKEN,
            field="availability",
            detail={"token": text},
        )
    ]


def _normalize_token(value: str) -> str:
    text = unicodedata.normalize("NFKC", value).casefold().strip()
    return _WHITESPACE_RE.sub(" ", text)
