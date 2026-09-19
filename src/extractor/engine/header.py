"""Localización del ancla de cabecera."""

from __future__ import annotations

import re

from extractor.domain.models import Line
from extractor.domain.profile import HeaderAnchor


def locate_header_index(lines: list[Line], anchor: HeaderAnchor | None) -> int | None:
    """Índice de la línea de cabecera, o None si no hay ancla / no se encontró."""
    if anchor is None:
        return None
    for index, line in enumerate(lines):
        if _matches(line.text, anchor):
            return index
    return None


def lines_after_header(lines: list[Line], anchor: HeaderAnchor | None) -> list[Line]:
    """Recorta líneas anteriores al ancla (+ offset_lines)."""
    if anchor is None:
        return list(lines)
    header_index = locate_header_index(lines, anchor)
    if header_index is None:
        return list(lines)
    start = header_index + 1 + anchor.offset_lines
    if start < 0:
        start = 0
    return lines[start:]


def _matches(text: str, anchor: HeaderAnchor) -> bool:
    if anchor.match == "exact":
        return text == anchor.text
    if anchor.match == "contains":
        return anchor.text in text
    return re.search(anchor.text, text) is not None
