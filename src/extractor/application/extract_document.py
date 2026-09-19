"""Caso de uso: extraer filas de un documento."""

from __future__ import annotations

import base64
import hashlib
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal, Protocol

from extractor.adapters.fetch.http_fetcher import Fetcher
from extractor.adapters.ocr.base import OcrEngine
from extractor.adapters.ocr.tesseract import TesseractOcr
from extractor.adapters.readers.base import DocumentReader
from extractor.adapters.readers.image_reader import ImageReader
from extractor.adapters.readers.pdf_ocr import ocr_pdf_pages
from extractor.adapters.readers.pdfplumber_tables import extract_page_tables
from extractor.domain.errors import (
    DocumentTooLargeError,
    DocumentUnreadableError,
    FingerprintMismatchError,
    InvalidRequestError,
    NoRowsFoundError,
    Sha256MismatchError,
    UnsupportedContentTypeError,
)
from extractor.domain.fingerprint import compare_components, compute_fingerprint
from extractor.domain.issues import IssueCode
from extractor.domain.layout import text_density
from extractor.domain.models import Diagnostics, Page, Row, Word
from extractor.domain.profile import Profile
from extractor.engine.filters import DraftRow, apply_filters, should_stop
from extractor.engine.header import lines_after_header, text_matches_anchor
from extractor.engine.lines import group_words_into_lines
from extractor.engine.merge import merge_multiline_rows
from extractor.engine.ocr_decision import decide_ocr
from extractor.engine.pages import select_pages
from extractor.engine.parse_rows import count_severity, draft_to_row, issues_by_code
from extractor.engine.strategies import get_strategy
from extractor.engine.strategies.base import Strategy
from extractor.engine.strategies.ruling import RulingStrategy
from extractor.observability.metrics import inc_fingerprint_mismatch

CROSS_BOUNDARY_WARNING_THRESHOLD = 0.02

SUPPORTED_CONTENT_TYPES = frozenset(
    {
        "application/pdf",
        "image/png",
        "image/jpeg",
        "image/tiff",
    }
)


class Clock(Protocol):
    def elapsed_ms(self, start: float) -> int: ...


@dataclass(frozen=True)
class DocumentInput:
    content_type: str
    filename: str | None = None
    url: str | None = None
    inline_base64: str | None = None
    sha256: str | None = None
    password: str | None = None


@dataclass(frozen=True)
class ExtractOptions:
    ocr: Literal["never", "auto", "force"] = "auto"
    max_pages: int = 200
    include_bbox: bool = True
    include_raw_words: bool = False
    fail_on_fingerprint_mismatch: bool = True


@dataclass(frozen=True)
class OcrSettings:
    enabled: bool = False
    density_threshold: float = 5.0
    min_confidence: float = 70.0
    tesseract_cmd: str = "tesseract"


@dataclass(frozen=True)
class LayoutInfo:
    fingerprint: str
    expected_fingerprint: str | None
    matched: bool
    page_count: int
    pages_processed: int
    page_geometry: dict[str, float | int]


@dataclass(frozen=True)
class ExtractResult:
    engine_version: str
    profile_version: int
    layout: LayoutInfo
    rows: list[Row]
    diagnostics: Diagnostics


class SystemClock:
    def elapsed_ms(self, start: float) -> int:
        return int((time.perf_counter() - start) * 1000)


def extract_document(
    *,
    document: DocumentInput,
    profile: Profile,
    options: ExtractOptions,
    fetcher: Fetcher,
    reader_for: Callable[[str], DocumentReader],
    clock: Clock | None = None,
    engine_version: str = "1.0.0",
    max_document_bytes: int = 52_428_800,
    ocr_settings: OcrSettings | None = None,
    ocr_engine: OcrEngine | None = None,
) -> ExtractResult:
    """Orquesta el pipeline de extraccion (pasos 1-14)."""
    timer = clock or SystemClock()
    started = time.perf_counter()
    ocr_cfg = ocr_settings if ocr_settings is not None else OcrSettings()

    data = _load_bytes(document, fetcher=fetcher, max_document_bytes=max_document_bytes)
    _verify_sha256(data, document.sha256)

    if document.content_type not in SUPPORTED_CONTENT_TYPES:
        raise UnsupportedContentTypeError(
            f"Unsupported content type: {document.content_type}",
            detail={"content_type": document.content_type},
        )

    password = document.password or profile.document.password
    pages, ocr_used = _load_pages(
        data=data,
        content_type=document.content_type,
        password=password,
        options=options,
        ocr_cfg=ocr_cfg,
        reader_for=reader_for,
        ocr_engine=ocr_engine,
    )
    if not pages:
        raise DocumentUnreadableError("PDF has zero pages.", detail={"reason": "zero_pages"})

    if len(pages) > options.max_pages:
        raise DocumentTooLargeError(
            "Document exceeds max_pages.",
            detail={"pages": len(pages), "max_pages": options.max_pages},
        )

    page1 = pages[0]
    lines1 = group_words_into_lines(
        page1.words,
        page=page1.number,
        row_tolerance=profile.table.row_tolerance,
    )
    anchor = profile.table.header_anchor
    fp = compute_fingerprint(
        page1,
        lines1,
        header_anchor_text=anchor.text if anchor else None,
        header_match=anchor.match if anchor else "contains",
    )

    expected_fp = profile.layout_fingerprint
    matched = expected_fp is None or expected_fp == fp.fingerprint
    if expected_fp is not None and not matched:
        inc_fingerprint_mismatch()
        if options.fail_on_fingerprint_mismatch:
            changed: list[str] = []
            if profile.layout_components is not None:
                changed = list(compare_components(profile.layout_components, fp.components))
            raise FingerprintMismatchError(
                "Document layout does not match the profile fingerprint.",
                detail={
                    "expected": expected_fp,
                    "actual": fp.fingerprint,
                    "changed": changed,
                    "actual_components": fp.components.as_dict(),
                    "hint": "Call POST /v1/sample to rebuild the profile.",
                },
            )

    selected, skipped = select_pages(pages, profile.document)
    strategy = get_strategy(profile.table.strategy)
    draft_rows: list[DraftRow] = []
    dropped_by_reason: dict[str, int] = {}

    for page in selected:
        if profile.table.strategy == "ruling" and not ocr_used:
            page_drafts = _drafts_from_ruling(
                data=data,
                page_number=page.number,
                profile=profile,
                dropped_by_reason=dropped_by_reason,
            )
        else:
            page_drafts = _drafts_from_lines(
                page_number=page.number,
                words=page.words,
                profile=profile,
                strategy=strategy,
                dropped_by_reason=dropped_by_reason,
            )

        page_drafts = merge_multiline_rows(page_drafts, profile)
        for draft in page_drafts:
            apply_filters(draft, profile)
            if draft.dropped:
                reason = draft.drop_reason or "filtered"
                dropped_by_reason[reason] = dropped_by_reason.get(reason, 0) + 1
            else:
                draft_rows.append(draft)

    rows: list[Row] = [
        draft_to_row(
            draft,
            row_index=index,
            profile=profile,
            include_bbox=options.include_bbox,
            ocr_used=ocr_used,
            ocr_min_confidence=ocr_cfg.min_confidence,
        )
        for index, draft in enumerate(draft_rows)
    ]

    if not rows:
        raise NoRowsFoundError(
            "No rows extracted with the given profile.",
            detail={"pages_processed": len(selected)},
        )

    err_count, warn_count = count_severity(rows)
    issue_counts = issues_by_code(rows)
    diagnostics = Diagnostics(
        rows_extracted=len(rows),
        rows_dropped=sum(dropped_by_reason.values()),
        rows_with_errors=err_count,
        rows_with_warnings=warn_count,
        issues_by_code=issue_counts,
        dropped_by_reason=dict(sorted(dropped_by_reason.items())),
        pages_processed=len(selected),
        pages_skipped=skipped,
        ocr_used=ocr_used,
        ocr_mean_confidence=_mean_ocr_confidence(pages) if ocr_used else None,
        strategy_used=profile.table.strategy,
        duration_ms=timer.elapsed_ms(started),
        warnings=_boundary_cross_warnings(rows, issue_counts),
        effective_profile=profile.model_dump(mode="json") if options.include_raw_words else None,
    )

    layout = LayoutInfo(
        fingerprint=fp.fingerprint,
        expected_fingerprint=expected_fp,
        matched=matched,
        page_count=len(pages),
        pages_processed=len(selected),
        page_geometry={
            "width": page1.width,
            "height": page1.height,
            "rotation": page1.rotation,
        },
    )

    return ExtractResult(
        engine_version=engine_version,
        profile_version=profile.version,
        layout=layout,
        rows=rows,
        diagnostics=diagnostics,
    )


def _load_pages(
    *,
    data: bytes,
    content_type: str,
    password: str | None,
    options: ExtractOptions,
    ocr_cfg: OcrSettings,
    reader_for: Callable[[str], DocumentReader],
    ocr_engine: OcrEngine | None,
) -> tuple[list[Page], bool]:
    is_image = content_type.startswith("image/")
    native_pages: list[Page] = []
    if is_image:
        density = 0.0
    else:
        native_reader = reader_for(content_type)
        native_pages = native_reader.read(data, password=password)
        density = text_density(native_pages)

    decision = decide_ocr(
        content_type=content_type,
        density=density,
        mode=options.ocr,
        density_threshold=ocr_cfg.density_threshold,
    )
    if decision == "unreadable":
        raise DocumentUnreadableError(
            "Document has no native text layer and OCR is disabled for this request.",
            detail={"reason": "no_text_ocr_never", "density": density},
        )
    if decision == "native":
        return native_pages, False

    # decision == "ocr"
    if not ocr_cfg.enabled:
        if density > 0.0 and not is_image:
            # OCR desactivado: seguir con texto nativo si existe capa de texto.
            return native_pages, False
        raise DocumentUnreadableError(
            "OCR is required for this document but OCR_ENABLED is false.",
            detail={"reason": "ocr_disabled", "density": density},
        )
    engine = (
        ocr_engine if ocr_engine is not None else TesseractOcr(tesseract_cmd=ocr_cfg.tesseract_cmd)
    )
    if is_image:
        pages = ImageReader(engine).read(data)
    else:
        pages = ocr_pdf_pages(data, engine, password=password)
    return pages, True


def _mean_ocr_confidence(pages: list[Page]) -> float | None:
    values = [
        word.confidence for page in pages for word in page.words if word.confidence is not None
    ]
    if not values:
        return None
    return round(sum(values) / len(values), 1)


def _drafts_from_lines(
    *,
    page_number: int,
    words: list[Word],
    profile: Profile,
    strategy: Strategy,
    dropped_by_reason: dict[str, int],
) -> list[DraftRow]:
    lines = group_words_into_lines(
        words,
        page=page_number,
        row_tolerance=profile.table.row_tolerance,
    )
    use_header = profile.table.header_anchor is not None and (
        profile.table.header_anchor.on_every_page or page_number == 1
    )
    data_lines = (
        lines_after_header(lines, profile.table.header_anchor) if use_header else list(lines)
    )

    typed_kept = []
    for line in data_lines:
        if should_stop(line.text, profile.table.stop_patterns):
            dropped_by_reason["matched_stop_pattern"] = (
                dropped_by_reason.get("matched_stop_pattern", 0) + 1
            )
            break
        typed_kept.append(line)

    cut = strategy.cut(typed_kept, profile)
    page_drafts: list[DraftRow] = []
    for line, (cells, geom_issues) in zip(typed_kept, cut, strict=True):
        cell_map = {cell.role: cell.raw for cell in cells}
        role_map: dict[str, str] = {col.role: cell_map.get(col.role, "") for col in profile.columns}
        confidences = [word.confidence for word in line.words if word.confidence is not None]
        page_drafts.append(
            DraftRow(
                page=page_number,
                source_lines=[line.line_index],
                cells=role_map,
                issues=list(geom_issues),
                top=line.top,
                bottom=line.bottom,
                x0=line.x0,
                x1=line.x1,
                ocr_confidences=confidences,
            )
        )
    return page_drafts


def _drafts_from_ruling(
    *,
    data: bytes,
    page_number: int,
    profile: Profile,
    dropped_by_reason: dict[str, int],
) -> list[DraftRow]:
    ruling = get_strategy("ruling")
    if not isinstance(ruling, RulingStrategy):
        raise TypeError("ruling strategy is not registered")
    tables = extract_page_tables(data, page_number=page_number, ruling=profile.table.ruling)
    table_rows = ruling.cut_tables(tables, profile)

    use_header = profile.table.header_anchor is not None and (
        profile.table.header_anchor.on_every_page or page_number == 1
    )
    start = 0
    anchor = profile.table.header_anchor
    if use_header and anchor is not None:
        header_index: int | None = None
        for index, (_cells, _issues, joined) in enumerate(table_rows):
            if text_matches_anchor(joined, anchor):
                header_index = index
                break
        if header_index is not None:
            start = header_index + 1 + anchor.offset_lines

    page_drafts: list[DraftRow] = []
    for row_index, (cells, geom_issues, joined) in enumerate(table_rows[start:], start=start):
        if should_stop(joined, profile.table.stop_patterns):
            dropped_by_reason["matched_stop_pattern"] = (
                dropped_by_reason.get("matched_stop_pattern", 0) + 1
            )
            break
        cell_map = {cell.role: cell.raw for cell in cells}
        role_map: dict[str, str] = {col.role: cell_map.get(col.role, "") for col in profile.columns}
        page_drafts.append(
            DraftRow(
                page=page_number,
                source_lines=[row_index],
                cells=role_map,
                issues=list(geom_issues),
            )
        )
    return page_drafts


def _boundary_cross_warnings(rows: list[Row], issue_counts: dict[str, int]) -> list[str]:
    """Guarda operativa: >2% de filas con TEXT_CROSSES_BOUNDARY."""
    if not rows:
        return []
    code = IssueCode.TEXT_CROSSES_BOUNDARY.value
    cross_words = issue_counts.get(code, 0)
    if cross_words == 0:
        return []
    rows_with_cross = sum(
        1
        for row in rows
        if any(issue.code == IssueCode.TEXT_CROSSES_BOUNDARY for issue in row.issues)
    )
    ratio = rows_with_cross / len(rows)
    if ratio <= CROSS_BOUNDARY_WARNING_THRESHOLD:
        return []
    percent = ratio * 100.0
    return [
        (
            f"{cross_words} palabras cruzan un limite de columna "
            f"({percent:.1f}% de las filas) - revisar column_boundaries"
        )
    ]


def _load_bytes(
    document: DocumentInput,
    *,
    fetcher: Fetcher,
    max_document_bytes: int,
) -> bytes:
    has_url = bool(document.url)
    has_inline = bool(document.inline_base64)
    if has_url == has_inline:
        raise InvalidRequestError(
            "Provide exactly one of url or inline_base64.",
            detail={},
        )

    if document.url:
        data = fetcher.fetch(document.url)
    else:
        assert document.inline_base64 is not None
        try:
            data = base64.b64decode(document.inline_base64, validate=True)
        except Exception as exc:
            raise DocumentUnreadableError(
                "inline_base64 is not valid base64.",
                detail={"reason": "bad_base64"},
            ) from exc

    if len(data) > max_document_bytes:
        raise DocumentTooLargeError(
            "Document exceeds MAX_DOCUMENT_BYTES.",
            detail={"size": len(data), "max_bytes": max_document_bytes},
        )
    return data


def _verify_sha256(data: bytes, expected: str | None) -> None:
    if expected is None:
        return
    actual = hashlib.sha256(data).hexdigest()
    normalized = expected.removeprefix("sha256:")
    if actual != normalized:
        raise Sha256MismatchError(
            "Document sha256 does not match.",
            detail={"expected": normalized, "actual": actual},
        )
