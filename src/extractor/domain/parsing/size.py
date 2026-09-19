"""Parser de tamaño con dimensión explícita del perfil."""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from extractor.domain.issues import Issue, IssueCode, make_issue
from extractor.domain.models import Size, SizeDimension
from extractor.domain.profile import SizeConfig, SizePattern


@dataclass(frozen=True, slots=True)
class _Match:
    magnitude: Decimal
    unit: str
    dimension: SizeDimension
    raw: str
    pattern_index: int


def parse_size(
    text: str,
    cfg: SizeConfig | None = None,
    *,
    plant_name: str = "",
) -> tuple[Size | None, list[Issue]]:
    """Parsea tamaño. No lanza excepciones."""
    config = cfg if cfg is not None else SizeConfig()
    issues: list[Issue] = []
    source = text.strip()

    if source == "" and plant_name.strip():
        recovered_matches = _collect_matches(plant_name, config.patterns)
        if recovered_matches:
            source = recovered_matches[0].raw
            issues.append(
                make_issue(
                    IssueCode.SIZE_RECOVERED_FROM_NAME,
                    field="size",
                    detail="size column empty; recovered from plant_name",
                )
            )

    if source == "":
        return _no_match(config, issues)

    matches = _collect_matches(source, config.patterns)
    if not matches:
        return _no_match(config, issues)

    if len(matches) == 1:
        return _to_size(matches[0]), issues

    dimensions = {match.dimension for match in matches}
    if len(dimensions) == 1:
        return _to_size(matches[0]), issues

    if config.on_multiple_matches == "first":
        # Primera coincidencia según el orden de patterns del perfil.
        first = min(matches, key=lambda item: item.pattern_index)
        return _to_size(first), issues

    return None, [
        *issues,
        make_issue(
            IssueCode.SIZE_AMBIGUOUS,
            field="size",
            detail={
                "readings": [
                    {
                        "magnitude": format(match.magnitude, "f"),
                        "unit": match.unit,
                        "dimension": match.dimension,
                        "raw": match.raw,
                    }
                    for match in matches
                ]
            },
        ),
    ]


def _no_match(
    config: SizeConfig,
    issues: list[Issue],
) -> tuple[Size | None, list[Issue]]:
    if config.on_no_match == "null":
        return None, issues
    return None, [
        *issues,
        make_issue(
            IssueCode.SIZE_UNRECOGNIZED,
            field="size",
            detail="no size pattern matched",
        ),
    ]


def _collect_matches(text: str, patterns: list[SizePattern]) -> list[_Match]:
    found: list[_Match] = []
    for index, pattern in enumerate(patterns):
        compiled = re.compile(pattern.regex)
        for match in compiled.finditer(text):
            raw_value = match.group("v") if "v" in match.re.groupindex else match.group(0)
            try:
                magnitude = Decimal(raw_value)
            except (InvalidOperation, TypeError, ValueError):
                continue
            if magnitude <= 0:
                continue
            found.append(
                _Match(
                    magnitude=magnitude,
                    unit=pattern.unit,
                    dimension=pattern.dimension,
                    raw=match.group(0),
                    pattern_index=index,
                )
            )
    return found


def _to_size(match: _Match) -> Size:
    return Size(
        magnitude=match.magnitude,
        unit=match.unit,
        dimension=match.dimension,
        raw=match.raw,
    )
