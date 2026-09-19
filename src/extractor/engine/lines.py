"""Agrupado de palabras en líneas por proximidad vertical."""

from __future__ import annotations

from extractor.domain.layout import sort_words
from extractor.domain.models import Line, Word


def group_words_into_lines(
    words: list[Word],
    *,
    page: int,
    row_tolerance: float = 2.5,
) -> list[Line]:
    """Agrupa palabras en líneas con media ponderada por ancho del top."""
    if not words:
        return []

    ordered = sort_words(words)
    lines: list[Line] = []

    current_words: list[Word] = [ordered[0]]
    current_top = ordered[0].top
    current_weight = max(ordered[0].x1 - ordered[0].x0, 0.1)

    for word in ordered[1:]:
        if abs(word.top - current_top) <= row_tolerance:
            width = max(word.x1 - word.x0, 0.1)
            current_top = (current_top * current_weight + word.top * width) / (
                current_weight + width
            )
            current_weight += width
            current_words.append(word)
        else:
            lines.append(_close_line(current_words, page=page, line_index=len(lines)))
            current_words = [word]
            current_top = word.top
            current_weight = max(word.x1 - word.x0, 0.1)

    lines.append(_close_line(current_words, page=page, line_index=len(lines)))
    return lines


def _close_line(words: list[Word], *, page: int, line_index: int) -> Line:
    # Dentro de la línea el orden de lectura es izquierda→derecha (x0), no por top.
    ordered = sorted(
        words,
        key=lambda word: (round(word.x0, 1), round(word.top, 1), word.text),
    )
    return Line(
        words=ordered,
        top=round(sum(word.top for word in ordered) / len(ordered), 1),
        x0=round(min(word.x0 for word in ordered), 1),
        x1=round(max(word.x1 for word in ordered), 1),
        bottom=round(max(word.bottom for word in ordered), 1),
        page=page,
        line_index=line_index,
    )
