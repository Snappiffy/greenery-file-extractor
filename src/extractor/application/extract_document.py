"""Caso de uso: extraer filas de un documento."""

from __future__ import annotations

import base64
import hashlib
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal, Protocol

from extractor.adapters.fetch.http_fetcher import Fetcher
from extractor.adapters.readers.base import DocumentReader
from extractor.domain.errors import (
    DocumentTooLargeError,
    DocumentUnreadableError,
    FingerprintMismatchError,
    InvalidRequestError,
    NoRowsFoundError,
    Sha256MismatchError,
    UnsupportedContentTypeError,
)
from extractor.domain.fingerprint import compute_fingerprint
from extractor.domain.models import Diagnostics, Row
from extractor.domain.profile import Profile
from extractor.engine.filters import DraftRow, apply_filters, should_stop
from extractor.engine.header import lines_after_header
from extractor.engine.lines import group_words_into_lines
from extractor.engine.merge import merge_multiline_rows
from extractor.engine.pages import select_pages
from extractor.engine.parse_rows import count_severity, draft_to_row, issues_by_code
from extractor.engine.strategies import get_strategy

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
) -> ExtractResult:
    """Orquesta el pipeline de extraccion (pasos 1-14)."""
    timer = clock or SystemClock()
    started = time.perf_counter()

    data = _load_bytes(document, fetcher=fetcher, max_document_bytes=max_document_bytes)
    _verify_sha256(data, document.sha256)

    if document.content_type not in SUPPORTED_CONTENT_TYPES:
        raise UnsupportedContentTypeError(
            f"Unsupported content type: {document.content_type}",
            detail={"content_type": document.content_type},
        )
    if document.content_type != "application/pdf":
        raise UnsupportedContentTypeError(
            "Only application/pdf is implemented in this milestone.",
            detail={"content_type": document.content_type},
        )

    reader = reader_for(document.content_type)
    password = document.password or profile.document.password
    pages = reader.read(data, password=password)
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
    if options.fail_on_fingerprint_mismatch and expected_fp is not None and not matched:
        raise FingerprintMismatchError(
            "Document layout does not match the profile fingerprint.",
            detail={
                "expected": expected_fp,
                "actual": fp.fingerprint,
                "changed": [],
                "actual_components": fp.components.as_dict(),
                "hint": "Call POST /v1/sample to rebuild the profile.",
            },
        )

    selected, skipped = select_pages(pages, profile.document)
    strategy = get_strategy(profile.table.strategy)
    draft_rows: list[DraftRow] = []
    dropped_by_reason: dict[str, int] = {}

    for page in selected:
        lines = group_words_into_lines(
            page.words,
            page=page.number,
            row_tolerance=profile.table.row_tolerance,
        )
        use_header = profile.table.header_anchor is not None and (
            profile.table.header_anchor.on_every_page or page.number == 1
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
            role_map: dict[str, str] = {
                col.role: cell_map.get(col.role, "") for col in profile.columns
            }
            page_drafts.append(
                DraftRow(
                    page=page.number,
                    source_lines=[line.line_index],
                    cells=role_map,
                    issues=list(geom_issues),
                    top=line.top,
                    bottom=line.bottom,
                    x0=line.x0,
                    x1=line.x1,
                )
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
        )
        for index, draft in enumerate(draft_rows)
    ]

    if not rows:
        raise NoRowsFoundError(
            "No rows extracted with the given profile.",
            detail={"pages_processed": len(selected)},
        )

    err_count, warn_count = count_severity(rows)
    diagnostics = Diagnostics(
        rows_extracted=len(rows),
        rows_dropped=sum(dropped_by_reason.values()),
        rows_with_errors=err_count,
        rows_with_warnings=warn_count,
        issues_by_code=issues_by_code(rows),
        dropped_by_reason=dict(sorted(dropped_by_reason.items())),
        pages_processed=len(selected),
        pages_skipped=skipped,
        ocr_used=False,
        ocr_mean_confidence=None,
        strategy_used=profile.table.strategy,
        duration_ms=timer.elapsed_ms(started),
        warnings=[],
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
