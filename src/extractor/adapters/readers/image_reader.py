"""Lector de imágenes vía OCR."""

from __future__ import annotations

from io import BytesIO

from PIL import Image, UnidentifiedImageError

from extractor.adapters.ocr.base import OcrEngine
from extractor.domain.errors import DocumentUnreadableError
from extractor.domain.models import Page


class ImageReader:
    """Abre PNG/JPEG/TIFF y obtiene palabras con el motor OCR."""

    def __init__(self, ocr: OcrEngine) -> None:
        self._ocr = ocr

    def read(self, data: bytes, *, password: str | None = None) -> list[Page]:
        del password  # las imágenes no llevan contraseña PDF
        if not data:
            raise DocumentUnreadableError(
                "Document is empty.",
                detail={"reason": "empty"},
            )
        try:
            image = Image.open(BytesIO(data))
            image.load()
        except UnidentifiedImageError as exc:
            raise DocumentUnreadableError(
                "Unable to open image.",
                detail={"reason": "open_failed"},
            ) from exc
        except OSError as exc:
            raise DocumentUnreadableError(
                "Unable to open image.",
                detail={"reason": "open_failed", "error": str(exc)},
            ) from exc

        rgb = image.convert("RGB")
        width = float(rgb.width)
        height = float(rgb.height)
        words = self._ocr.image_to_words(rgb, scale_x=1.0, scale_y=1.0)
        return [
            Page(
                number=1,
                width=round(width, 1),
                height=round(height, 1),
                rotation=0,
                words=words,
            )
        ]
