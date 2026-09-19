"""OCR de páginas PDF renderizadas con PyMuPDF."""

from __future__ import annotations

import pymupdf
from PIL import Image

from extractor.adapters.ocr.base import OcrEngine
from extractor.domain.errors import DocumentUnreadableError
from extractor.domain.models import Page

DEFAULT_OCR_DPI = 200.0


def ocr_pdf_pages(
    data: bytes,
    ocr: OcrEngine,
    *,
    password: str | None = None,
    dpi: float = DEFAULT_OCR_DPI,
) -> list[Page]:
    """Renderiza cada página a imagen y aplica OCR (coordenadas en puntos PDF)."""
    if not data:
        raise DocumentUnreadableError(
            "Document is empty.",
            detail={"reason": "empty"},
        )
    try:
        document = pymupdf.open(stream=data, filetype="pdf")
    except Exception as exc:
        raise DocumentUnreadableError(
            "Unable to open PDF for OCR.",
            detail={"reason": "open_failed", "error": str(exc)},
        ) from exc

    try:
        if document.is_encrypted:
            if not password:
                raise DocumentUnreadableError(
                    "PDF is encrypted and no password was provided.",
                    detail={"reason": "encrypted"},
                )
            if not document.authenticate(password):
                raise DocumentUnreadableError(
                    "PDF password is incorrect.",
                    detail={"reason": "bad_password"},
                )
        if document.page_count == 0:
            raise DocumentUnreadableError(
                "PDF has zero pages.",
                detail={"reason": "zero_pages"},
            )

        zoom = dpi / 72.0
        matrix = pymupdf.Matrix(zoom, zoom)
        scale = 72.0 / dpi
        pages: list[Page] = []
        for index in range(document.page_count):
            page = document.load_page(index)
            rect = page.rect
            pixmap = page.get_pixmap(matrix=matrix, alpha=False)
            image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
            words = ocr.image_to_words(image, scale_x=scale, scale_y=scale)
            pages.append(
                Page(
                    number=index + 1,
                    width=round(float(rect.width), 1),
                    height=round(float(rect.height), 1),
                    rotation=int(page.rotation),
                    words=words,
                )
            )
        return pages
    finally:
        document.close()
