"""Filtros de filas y stop_patterns."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from extractor.domain.issues import Issue
from extractor.domain.profile import FiltersConfig, Profile


@dataclass
class DraftRow:
    """Fila intermedia antes del parseo tipado."""

    page: int
    source_lines: list[int]
    cells: dict[str, str]
    issues: list[Issue] = field(default_factory=list)
    top: float = 0.0
    bottom: float = 0.0
    x0: float = 0.0
    x1: float = 0.0
    dropped: bool = False
    drop_reason: str | None = None


def should_stop(line_text: str, stop_patterns: list[str]) -> bool:
    return any(re.search(pattern, line_text) is not None for pattern in stop_patterns)


def apply_filters(row: DraftRow, profile: Profile) -> DraftRow:
    """Marca la fila como dropped si encaja en filters del perfil."""
    filters = profile.filters
    plant = row.cells.get("plant_name", "")

    for pattern in filters.drop_rows_matching.get("plant_name", []):
        if re.search(pattern, plant) is not None:
            row.dropped = True
            row.drop_reason = "matched_drop_pattern"
            return row

    if len(plant.strip()) < filters.min_plant_name_length:
        row.dropped = True
        row.drop_reason = "min_name_length"
        return row

    if _all_empty(row, filters):
        row.dropped = True
        row.drop_reason = "empty_row"
        return row

    return row


def _all_empty(row: DraftRow, filters: FiltersConfig) -> bool:
    roles = filters.drop_rows_where_all_empty
    if not roles:
        return False
    return all(not row.cells.get(role, "").strip() for role in roles)
