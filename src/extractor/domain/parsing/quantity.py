"""Parser de cantidad. None no es 0."""

from __future__ import annotations

import re
import unicodedata

from extractor.domain.issues import Issue, IssueCode, make_issue
from extractor.domain.profile import QuantityConfig

_NON_NUMERIC_TOKENS = frozenset({"-", "n/a", "na", "tbd", "call"})
_THOUSANDS_RE = re.compile(r"[, ]")


def parse_quantity(
    text: str,
    cfg: QuantityConfig | None = None,
) -> tuple[int | None, list[Issue]]:
    """Parsea una cantidad a int o None. No lanza excepciones."""
    config = cfg if cfg is not None else QuantityConfig()
    normalized = unicodedata.normalize("NFKC", text).strip()

    if normalized == "":
        if config.empty_means == "zero":
            return 0, []
        return None, []

    lowered = normalized.casefold()
    if lowered in _NON_NUMERIC_TOKENS:
        return _non_numeric(normalized, config)

    cleaned = _THOUSANDS_RE.sub("", normalized)
    if cleaned.startswith("+"):
        cleaned = cleaned[1:]

    try:
        # Int primero: evita float. Acepta enteros con signo.
        if re.fullmatch(r"-?\d+", cleaned) is None:
            return _non_numeric(normalized, config)
        value = int(cleaned)
    except ValueError:
        return _non_numeric(normalized, config)

    if value < 0:
        return None, [
            make_issue(
                IssueCode.QUANTITY_UNPARSEABLE,
                field="quantity",
                detail=f"negative quantity: {normalized!r}",
            )
        ]
    return value, []


def _non_numeric(
    original: str,
    config: QuantityConfig,
) -> tuple[int | None, list[Issue]]:
    if config.on_non_numeric == "null":
        return None, []
    return None, [
        make_issue(
            IssueCode.QUANTITY_UNPARSEABLE,
            field="quantity",
            detail=f"non-numeric quantity: {original!r}",
        )
    ]
