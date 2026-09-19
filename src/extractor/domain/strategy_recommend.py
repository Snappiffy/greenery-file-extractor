"""Heurística de estrategia recomendada a partir de evidencia de layout."""

from __future__ import annotations

from extractor.domain.layout import ColumnCandidate


def recommend_strategy(
    candidates: list[ColumnCandidate],
    *,
    vertical_rulings: list[float],
) -> str:
    """si hay verticales → ruling; si columnas estables → columns; si no → regex."""
    if vertical_rulings:
        return "ruling"
    strong = strong_column_candidates(candidates)
    if _columns_look_stable(strong):
        return "columns"
    return "regex"


def strong_column_candidates(
    candidates: list[ColumnCandidate],
    *,
    relative_floor: float = 0.5,
) -> list[ColumnCandidate]:
    """Conserva candidatos con support alto respecto al máximo (ruido de palabras)."""
    if not candidates:
        return []
    max_support = max(candidate.support for candidate in candidates)
    floor = max(2, int(max_support * relative_floor))
    return [candidate for candidate in candidates if candidate.support >= floor]


def _columns_look_stable(candidates: list[ColumnCandidate]) -> bool:
    if len(candidates) < 2:
        return False
    supports = [candidate.support for candidate in candidates]
    mean = sum(supports) / len(supports)
    if mean < 2:
        return False
    variance = sum((value - mean) ** 2 for value in supports) / len(supports)
    std = variance**0.5
    # Soporte alto y estable: coeficiente de variación < 0.6
    return bool((std / mean) < 0.6)
