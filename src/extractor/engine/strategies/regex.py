"""Estrategia regex: una línea de texto → celdas por grupos nombrados."""

from __future__ import annotations

import re

from extractor.domain.issues import Issue, IssueCode, make_issue
from extractor.domain.models import Cell, Line
from extractor.domain.profile import Profile


class RegexStrategy:
    """Aplica `table.line_pattern` a cada línea agrupada."""

    def cut(
        self,
        lines: list[Line],
        profile: Profile,
    ) -> list[tuple[list[Cell], list[Issue]]]:
        pattern_text = profile.table.line_pattern
        if not pattern_text:
            return [([], []) for _ in lines]

        compiled = re.compile(pattern_text)
        results: list[tuple[list[Cell], list[Issue]]] = []
        for line in lines:
            match = compiled.search(line.text)
            issues: list[Issue] = []
            if match is None:
                issues.append(
                    make_issue(
                        IssueCode.LINE_PATTERN_NO_MATCH,
                        detail=f"line did not match line_pattern: {line.text!r}",
                    )
                )
                cells = [
                    Cell(role=column.role, raw="", index=column.index) for column in profile.columns
                ]
            else:
                cells = []
                for column in profile.columns:
                    raw = match.group(column.role)
                    cells.append(
                        Cell(
                            role=column.role,
                            raw="" if raw is None else raw,
                            index=column.index,
                        )
                    )
            results.append((cells, issues))
        return results
