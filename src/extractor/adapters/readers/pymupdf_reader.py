"""Lector de PDF con PyMuPDF."""

from __future__ import annotations

import pymupdf

from extractor.domain.errors import DocumentUnreadableError
from extractor.domain.layout import sort_words
from extractor.domain.models import Page, Word


class PyMuPdfReader:
    """Extrae palabras con bbox en orden determinista."""

    def read(self, data: bytes, *, password: str | None = None) -> list[Page]:
        if not data:
            raise DocumentUnreadableError(
                "Document is empty.",
                detail={"reason": "empty"},
            )

        try:
            document = pymupdf.open(stream=data, filetype="pdf")
        except Exception as exc:
            raise DocumentUnreadableError(
                "Unable to open PDF.",
                detail={"reason": "open_failed", "error": str(exc)},
            ) from exc

        try:
            return self._read_open_document(document, password=password)
        finally:
            document.close()

    def _read_open_document(
        self,
        document: pymupdf.Document,
        *,
        password: str | None,
    ) -> list[Page]:
        if document.is_encrypted:
            if not password:
                raise DocumentUnreadableError(
                    "PDF is encrypted and no password was provided.",
                    detail={"reason": "encrypted"},
                )
            authenticated = document.authenticate(password)
            if not authenticated:
                raise DocumentUnreadableError(
                    "PDF password is incorrect.",
                    detail={"reason": "bad_password"},
                )

        if document.page_count == 0:
            raise DocumentUnreadableError(
                "PDF has zero pages.",
                detail={"reason": "zero_pages"},
            )

        pages: list[Page] = []
        for index in range(document.page_count):
            page = document.load_page(index)
            rect = page.rect
            words = self._extract_words(page)
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

    def _extract_words(self, page: pymupdf.Page) -> list[Word]:
        raw_words = page.get_text("words")
        words: list[Word] = []
        for entry in raw_words:
            # (x0, y0, x1, y1, word, block_no, line_no, word_no)
            x0, y0, x1, y1, text, *_rest = entry
            if not text or not str(text).strip():
                continue
            words.append(
                Word(
                    text=str(text),
                    x0=round(float(x0), 1),
                    top=round(float(y0), 1),
                    x1=round(float(x1), 1),
                    bottom=round(float(y1), 1),
                )
            )
        return sort_words(words)
