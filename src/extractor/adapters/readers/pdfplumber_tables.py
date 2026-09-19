"""Extracción de tablas con líneas dibujadas vía pdfplumber."""

from __future__ import annotations

from io import BytesIO
from typing import Any

import pdfplumber

from extractor.domain.profile import RulingConfig


def extract_page_tables(
    data: bytes,
    *,
    page_number: int,
    ruling: RulingConfig | None = None,
) -> list[list[list[str | None]]]:
    """Devuelve las tablas de una página (1-based) como matrices de celdas."""
    settings = _table_settings(ruling)
    with pdfplumber.open(BytesIO(data)) as pdf:
        if page_number < 1 or page_number > len(pdf.pages):
            return []
        page = pdf.pages[page_number - 1]
        raw_tables = page.extract_tables(table_settings=settings) or []
        return [_normalize_table(table) for table in raw_tables]


def _table_settings(ruling: RulingConfig | None) -> dict[str, Any]:
    cfg = ruling if ruling is not None else RulingConfig()
    return {
        "vertical_strategy": cfg.vertical_strategy,
        "horizontal_strategy": cfg.horizontal_strategy,
        "snap_tolerance": cfg.snap_tolerance,
    }


def _normalize_table(table: list[list[Any]]) -> list[list[str | None]]:
    rows: list[list[str | None]] = []
    for row in table:
        cells: list[str | None] = []
        for cell in row:
            if cell is None:
                cells.append(None)
            else:
                text = str(cell).replace("\n", " ").strip()
                cells.append(text if text else None)
        rows.append(cells)
    return rows
