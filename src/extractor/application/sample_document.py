"""Caso de uso: muestrear evidencia de layout (POST /v1/sample)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from extractor.adapters.fetch.http_fetcher import Fetcher
from extractor.adapters.readers.base import DocumentReader
from extractor.adapters.readers.pdfplumber_rulings import extract_ruling_lines
from extractor.application.extract_document import (
    DocumentInput,
    _load_bytes,
    _verify_sha256,
)
from extractor.domain.errors import DocumentUnreadableError, UnsupportedContentTypeError
from extractor.domain.fingerprint import compute_fingerprint
from extractor.domain.layout import (
    ColumnCandidate,
    enrich_candidate_samples,
    find_column_candidates,
    is_scanned,
    text_density,
)
from extractor.domain.strategy_recommend import recommend_strategy, strong_column_candidates
from extractor.engine.lines import group_words_into_lines


@dataclass(frozen=True)
class SampleOptions:
    pages: list[int]
    max_lines_per_page: int = 120
    ocr: Literal["never", "auto", "force"] = "auto"


@dataclass(frozen=True)
class SampleLineOut:
    top: float
    x0: float
    x1: float
    text: str


@dataclass(frozen=True)
class SamplePageOut:
    number: int
    lines: list[SampleLineOut]
    column_candidates: list[ColumnCandidate]
    ruling_lines: dict[str, list[float]]


@dataclass(frozen=True)
class SampleResult:
    engine_version: str
    fingerprint: str
    page_count: int
    page_geometry: dict[str, float | int]
    is_scanned: bool
    text_density: float
    recommended_strategy: str
    pages: list[SamplePageOut]


def sample_document(
    *,
    document: DocumentInput,
    options: SampleOptions,
    fetcher: Fetcher,
    reader_for: Callable[[str], DocumentReader],
    engine_version: str = "1.0.0",
    max_document_bytes: int = 52_428_800,
) -> SampleResult:
    """Describe geometría del documento sin interpretar roles de negocio."""
    data = _load_bytes(document, fetcher=fetcher, max_document_bytes=max_document_bytes)
    _verify_sha256(data, document.sha256)

    if document.content_type != "application/pdf":
        raise UnsupportedContentTypeError(
            "Only application/pdf is supported for sample in this milestone.",
            detail={"content_type": document.content_type},
        )

    reader = reader_for(document.content_type)
    pages = reader.read(data, password=document.password)
    if not pages:
        raise DocumentUnreadableError("PDF has zero pages.", detail={"reason": "zero_pages"})

    page_numbers = options.pages or [1]
    selected = [page for page in pages if page.number in page_numbers]
    if not selected:
        selected = [pages[0]]

    page1 = pages[0]
    lines1 = group_words_into_lines(page1.words, page=page1.number)
    fp = compute_fingerprint(page1, lines1)

    sample_pages: list[SamplePageOut] = []
    for page in selected:
        lines = group_words_into_lines(page.words, page=page.number)
        capped = lines[: options.max_lines_per_page]
        raw_candidates = find_column_candidates(page.words, line_count=max(len(lines), 1))
        # Evidencia útil para el worker: columnas con support alto (sin ruido de palabras).
        candidates = strong_column_candidates(raw_candidates)
        data_lines = capped[1:] if len(capped) > 1 else capped
        candidates = enrich_candidate_samples(data_lines, candidates, sample_limit=3)

        rulings = extract_ruling_lines(data, page_number=page.number)
        sample_pages.append(
            SamplePageOut(
                number=page.number,
                lines=[
                    SampleLineOut(
                        top=round(line.top, 1),
                        x0=round(line.x0, 1),
                        x1=round(line.x1, 1),
                        text=line.text,
                    )
                    for line in capped
                ],
                column_candidates=candidates,
                ruling_lines={
                    "vertical": list(rulings.vertical),
                    "horizontal": list(rulings.horizontal),
                },
            )
        )

    strategy = "regex"
    if sample_pages:
        strategy = recommend_strategy(
            sample_pages[0].column_candidates,
            vertical_rulings=sample_pages[0].ruling_lines["vertical"],
        )

    return SampleResult(
        engine_version=engine_version,
        fingerprint=fp.fingerprint,
        page_count=len(pages),
        page_geometry={
            "width": page1.width,
            "height": page1.height,
            "rotation": page1.rotation,
        },
        is_scanned=is_scanned(pages),
        text_density=round(text_density(pages), 4),
        recommended_strategy=strategy,
        pages=sample_pages,
    )
