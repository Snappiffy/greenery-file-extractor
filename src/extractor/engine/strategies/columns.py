"""Estrategia columns: recorte por fronteras en x."""

from __future__ import annotations

from extractor.domain.issues import Issue, IssueCode, make_issue
from extractor.domain.models import Cell, Line, Word
from extractor.domain.profile import Profile


class ColumnsStrategy:
    """Asigna palabras a columnas por x0 frente a column_boundaries."""

    def cut(
        self,
        lines: list[Line],
        profile: Profile,
    ) -> list[tuple[list[Cell], list[Issue]]]:
        boundaries = profile.table.column_boundaries
        if boundaries is None:
            return [([], []) for _ in lines]
        tolerance = profile.table.boundary_tolerance
        role_by_index = {col.index: col.role for col in profile.columns}
        n_cols = len(boundaries) - 1

        results: list[tuple[list[Cell], list[Issue]]] = []
        for line in lines:
            buckets: list[list[Word]] = [[] for _ in range(n_cols)]
            issues: list[Issue] = []
            for word in line.words:
                index, crossed = _assign_column(word, boundaries, tolerance)
                buckets[index].append(word)
                if crossed:
                    issues.append(
                        make_issue(
                            IssueCode.TEXT_CROSSES_BOUNDARY,
                            field=role_by_index.get(index),
                            detail=(
                                f"word {word.text!r} crosses column boundary "
                                f"(x0={word.x0}, x1={word.x1})"
                            ),
                        )
                    )

            cells: list[Cell] = []
            for index in range(n_cols):
                role = role_by_index.get(index, f"col_{index}")
                text = " ".join(word.text for word in buckets[index])
                cells.append(Cell(role=role, raw=text, index=index))
            results.append((cells, issues))
        return results


def _assign_column(
    word: Word,
    boundaries: list[float],
    tolerance: float,
) -> tuple[int, bool]:
    """Devuelve (índice de columna, cruzó_frontera)."""
    n_cols = len(boundaries) - 1
    x0 = word.x0
    x1 = word.x1

    # 1) Intervalo nominal sin tolerancia.
    for i in range(n_cols):
        if boundaries[i] <= x0 < boundaries[i + 1]:
            crossed = x0 < boundaries[i + 1] <= x1
            return i, crossed

    # 2) Fuera de rango o solo alcanzable con tolerancia.
    if x0 < boundaries[0]:
        return 0, True
    if x0 >= boundaries[-1]:
        return n_cols - 1, True

    for i in range(n_cols):
        left = boundaries[i] - tolerance
        right = boundaries[i + 1] + tolerance
        if left <= x0 < right:
            return i, True

    return n_cols - 1, True
