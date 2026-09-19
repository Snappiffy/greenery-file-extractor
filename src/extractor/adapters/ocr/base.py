"""Protocolo del motor OCR."""

from __future__ import annotations

from typing import Protocol

from PIL import Image

from extractor.domain.models import Word


class OcrEngine(Protocol):
    """Convierte una imagen en palabras con bbox y confianza."""

    def image_to_words(
        self,
        image: Image.Image,
        *,
        scale_x: float = 1.0,
        scale_y: float = 1.0,
    ) -> list[Word]:
        """Devuelve palabras en coordenadas de página (tras escalar)."""
        ...
