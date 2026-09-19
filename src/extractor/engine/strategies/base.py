"""Protocolo de estrategias de recorte de columnas."""

from __future__ import annotations

from typing import Protocol

from extractor.domain.issues import Issue
from extractor.domain.models import Cell, Line
from extractor.domain.profile import Profile


class Strategy(Protocol):
    def cut(
        self,
        lines: list[Line],
        profile: Profile,
    ) -> list[tuple[list[Cell], list[Issue]]]:
        """Recorta cada línea en celdas + issues de geometría."""
        ...
