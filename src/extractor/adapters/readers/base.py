"""Protocolo de lectura de documentos."""

from __future__ import annotations

from typing import Protocol

from extractor.domain.models import Page


class DocumentReader(Protocol):
    """Traduce bytes de documento a páginas de dominio con palabras."""

    def read(self, data: bytes, *, password: str | None = None) -> list[Page]:
        """Abre el documento y devuelve páginas ordenadas (1-based)."""
        ...
