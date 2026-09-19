"""Motor OCR basado en Tesseract."""

from __future__ import annotations

import pytesseract
from PIL import Image

from extractor.domain.errors import DocumentUnreadableError
from extractor.domain.layout import sort_words
from extractor.domain.models import Word


class TesseractOcr:
    """Extrae palabras con confianza vía pytesseract."""

    def __init__(self, *, tesseract_cmd: str = "tesseract") -> None:
        self._tesseract_cmd = tesseract_cmd

    def image_to_words(
        self,
        image: Image.Image,
        *,
        scale_x: float = 1.0,
        scale_y: float = 1.0,
    ) -> list[Word]:
        previous = pytesseract.pytesseract.tesseract_cmd
        pytesseract.pytesseract.tesseract_cmd = self._tesseract_cmd
        try:
            payload = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
        except pytesseract.TesseractNotFoundError as exc:
            raise DocumentUnreadableError(
                "OCR requested but tesseract binary was not found.",
                detail={"reason": "tesseract_missing", "cmd": self._tesseract_cmd},
            ) from exc
        except pytesseract.TesseractError as exc:
            raise DocumentUnreadableError(
                "OCR failed while reading the document.",
                detail={"reason": "ocr_failed", "error": str(exc)},
            ) from exc
        finally:
            pytesseract.pytesseract.tesseract_cmd = previous

        words: list[Word] = []
        count = len(payload.get("text", []))
        for index in range(count):
            text = str(payload["text"][index] or "").strip()
            if not text:
                continue
            try:
                conf = float(payload["conf"][index])
            except (TypeError, ValueError):
                conf = -1.0
            if conf < 0:
                continue
            left = float(payload["left"][index])
            top = float(payload["top"][index])
            width = float(payload["width"][index])
            height = float(payload["height"][index])
            words.append(
                Word(
                    text=text,
                    x0=round(left * scale_x, 1),
                    top=round(top * scale_y, 1),
                    x1=round((left + width) * scale_x, 1),
                    bottom=round((top + height) * scale_y, 1),
                    confidence=round(conf, 1),
                )
            )
        return sort_words(words)
