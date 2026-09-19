"""Estrategia ruling: celdas desde pdfplumber.extract_tables()."""

from __future__ import annotations

from extractor.domain.issues import Issue
from extractor.domain.models import Cell, Line
from extractor.domain.profile import Profile


class RulingStrategy:
    """Mapea filas de tabla con líneas dibujadas a celdas por índice.

    El recorte real ocurre en `cut_tables` (necesita el PDF). `cut` sobre líneas
    de PyMuPDF no aplica: se mantiene por el protocolo Strategy y no se usa.
    """

    def cut(
        self,
        lines: list[Line],
        profile: Profile,
    ) -> list[tuple[list[Cell], list[Issue]]]:
        return [([], []) for _ in lines]

    def cut_tables(
        self,
        tables: list[list[list[str | None]]],
        profile: Profile,
    ) -> list[tuple[list[Cell], list[Issue], str]]:
        """Una entrada por fila de datos: (celdas, issues, texto unido)."""
        results: list[tuple[list[Cell], list[Issue], str]] = []
        for table in tables:
            for row in table:
                cells = _cells_from_row(row, profile)
                joined = _join_row(row)
                results.append((cells, [], joined))
        return results


def _cells_from_row(row: list[str | None], profile: Profile) -> list[Cell]:
    cells: list[Cell] = []
    for column in profile.columns:
        raw = ""
        if 0 <= column.index < len(row):
            value = row[column.index]
            raw = "" if value is None else value
        cells.append(Cell(role=column.role, raw=raw, index=column.index))
    return cells


def _join_row(row: list[str | None]) -> str:
    parts = [cell.strip() for cell in row if cell is not None and cell.strip()]
    return " ".join(parts)
