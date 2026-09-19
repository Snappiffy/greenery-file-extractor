"""Extracción de líneas de tabla (ruling) con pdfplumber."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

import pdfplumber


@dataclass(frozen=True)
class RulingLines:
    vertical: list[float]
    horizontal: list[float]


def extract_ruling_lines(data: bytes, *, page_number: int = 1) -> RulingLines:
    """Devuelve coordenadas de líneas dibujadas en la página (1-based)."""
    with pdfplumber.open(BytesIO(data)) as pdf:
        if page_number < 1 or page_number > len(pdf.pages):
            return RulingLines(vertical=[], horizontal=[])
        page = pdf.pages[page_number - 1]
        vertical: set[float] = set()
        horizontal: set[float] = set()
        for line in page.lines:
            x0 = float(line["x0"])
            x1 = float(line["x1"])
            top = float(line["top"])
            bottom = float(line["bottom"])
            if abs(x0 - x1) <= 0.5:
                vertical.add(round(x0, 1))
            if abs(top - bottom) <= 0.5:
                horizontal.add(round(top, 1))
        return RulingLines(
            vertical=sorted(vertical),
            horizontal=sorted(horizontal),
        )
