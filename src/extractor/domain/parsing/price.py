"""Parser de precio. Nunca usa float."""

from __future__ import annotations

import re
import unicodedata
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from extractor.domain.issues import Issue, IssueCode, make_issue
from extractor.domain.profile import PriceConfig

_TWO_PLACES = Decimal("0.01")
_RANGE_SPLIT_RE = re.compile(
    r"(?P<a>\d[\d.,]*)\s*(?:-|\u2013|to|/)\s*(?P<b>\d[\d.,]*)",
    re.IGNORECASE,
)


def parse_price(
    text: str,
    cfg: PriceConfig | None = None,
) -> tuple[Decimal | None, list[Issue]]:
    """Parsea un precio a Decimal cuantizado a 2 decimales. No lanza excepciones."""
    config = cfg if cfg is not None else PriceConfig()
    issues: list[Issue] = []

    normalized = unicodedata.normalize("NFKC", text).strip()
    if normalized == "":
        if config.empty_means == "zero":
            return Decimal("0.00"), issues
        return None, issues

    stripped = normalized
    for literal in config.strip:
        stripped = re.sub(re.escape(literal), "", stripped, flags=re.IGNORECASE)
    stripped = stripped.strip()
    if stripped == "":
        if config.empty_means == "zero":
            return Decimal("0.00"), issues
        return None, issues

    range_match = _RANGE_SPLIT_RE.fullmatch(stripped) or _RANGE_SPLIT_RE.search(stripped)
    if range_match and _looks_like_range(stripped, range_match):
        left = _to_decimal(range_match.group("a"), config)
        right = _to_decimal(range_match.group("b"), config)
        if left is None or right is None:
            return None, [
                make_issue(
                    IssueCode.PRICE_UNPARSEABLE,
                    field="price",
                    detail=f"unparseable price range: {normalized!r}",
                )
            ]
        issues.append(
            make_issue(
                IssueCode.PRICE_RANGE,
                field="price",
                detail=f"price range resolved with on_range={config.on_range}",
            )
        )
        if config.on_range == "issue":
            return None, issues
        chosen = min(left, right) if config.on_range == "min" else max(left, right)
        return _finalize(chosen, config, issues)

    parsed = _to_decimal(stripped, config)
    if parsed is None:
        return None, [
            make_issue(
                IssueCode.PRICE_UNPARSEABLE,
                field="price",
                detail=f"unparseable price: {normalized!r}",
            )
        ]
    return _finalize(parsed, config, issues)


def _looks_like_range(text: str, match: re.Match[str]) -> bool:
    """Evita tratar un solo número con guion suelto como rango vacío."""
    return match.group("a") is not None and match.group("b") is not None and match.group(0) in text


def _to_decimal(raw: str, config: PriceConfig) -> Decimal | None:
    cleaned = raw.strip()
    if config.thousands_separator:
        cleaned = cleaned.replace(config.thousands_separator, "")
    if config.decimal_separator and config.decimal_separator != ".":
        cleaned = cleaned.replace(config.decimal_separator, ".")
    cleaned = cleaned.strip()
    try:
        return Decimal(cleaned)
    except (InvalidOperation, ValueError):
        return None


def _finalize(
    value: Decimal,
    config: PriceConfig,
    issues: list[Issue],
) -> tuple[Decimal | None, list[Issue]]:
    quantized = value.quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)
    if quantized < 0:
        issues.append(
            make_issue(
                IssueCode.PRICE_NEGATIVE,
                field="price",
                detail=f"negative price: {quantized}",
            )
        )
    if quantized > config.max_reasonable:
        issues.append(
            make_issue(
                IssueCode.PRICE_IMPLAUSIBLE,
                field="price",
                detail=f"price {quantized} exceeds max_reasonable {config.max_reasonable}",
            )
        )
    return quantized, issues
