"""Serialización dominio → DTOs HTTP."""

from __future__ import annotations

from decimal import Decimal

from extractor.api.schemas import (
    BBoxOut,
    ColumnCandidateOut,
    DiagnosticsOut,
    ExtractResponse,
    IssueOut,
    LayoutOut,
    ParsedOut,
    RowOut,
    RulingLinesOut,
    SampleLineOut,
    SamplePageOut,
    SampleResponse,
    SizeOut,
)
from extractor.application.extract_document import ExtractResult
from extractor.application.sample_document import SampleResult
from extractor.domain.models import Row, Size


def serialize_extract_result(result: ExtractResult) -> ExtractResponse:
    return ExtractResponse(
        engine_version=result.engine_version,
        profile_version=result.profile_version,
        layout=LayoutOut(
            fingerprint=result.layout.fingerprint,
            expected_fingerprint=result.layout.expected_fingerprint,
            matched=result.layout.matched,
            page_count=result.layout.page_count,
            pages_processed=result.layout.pages_processed,
            page_geometry=result.layout.page_geometry,
        ),
        rows=[_serialize_row(row) for row in result.rows],
        diagnostics=DiagnosticsOut(
            rows_extracted=result.diagnostics.rows_extracted,
            rows_dropped=result.diagnostics.rows_dropped,
            rows_with_errors=result.diagnostics.rows_with_errors,
            rows_with_warnings=result.diagnostics.rows_with_warnings,
            issues_by_code=result.diagnostics.issues_by_code,
            dropped_by_reason=result.diagnostics.dropped_by_reason,
            pages_processed=result.diagnostics.pages_processed,
            pages_skipped=result.diagnostics.pages_skipped,
            ocr_used=result.diagnostics.ocr_used,
            ocr_mean_confidence=result.diagnostics.ocr_mean_confidence,
            strategy_used=result.diagnostics.strategy_used,
            duration_ms=result.diagnostics.duration_ms,
            warnings=result.diagnostics.warnings,
            effective_profile=result.diagnostics.effective_profile,
        ),
    )


def _serialize_row(row: Row) -> RowOut:
    parsed = row.parsed
    price = None if parsed.price is None else format(parsed.price, "f")
    size_out = None if parsed.size is None else _serialize_size(parsed.size)

    return RowOut(
        row_index=row.row_index,
        page=row.page,
        source_lines=row.source_lines,
        raw=row.raw,
        text=row.text,
        parsed=ParsedOut(
            plant_name=parsed.plant_name,
            size=size_out,
            price=price,
            quantity=parsed.quantity,
            availability=parsed.availability,
            grower_code=parsed.grower_code,
            notes=parsed.notes,
        ),
        issues=[
            IssueOut(
                code=issue.code.value,
                severity=issue.severity.value,
                field=issue.field,
                detail=issue.detail,
            )
            for issue in row.issues
        ],
        bbox=(
            None
            if row.bbox is None
            else BBoxOut(
                page=row.bbox.page,
                x0=row.bbox.x0,
                top=row.bbox.top,
                x1=row.bbox.x1,
                bottom=row.bbox.bottom,
            )
        ),
    )


def _serialize_size(size: Size) -> SizeOut:
    magnitude = size.magnitude
    mag = format(magnitude, "f") if isinstance(magnitude, Decimal) else str(magnitude)
    return SizeOut(
        magnitude=mag,
        unit=size.unit,
        dimension=size.dimension,
        raw=size.raw,
    )


def serialize_sample_result(result: SampleResult) -> SampleResponse:
    return SampleResponse(
        engine_version=result.engine_version,
        fingerprint=result.fingerprint,
        page_count=result.page_count,
        page_geometry=result.page_geometry,
        is_scanned=result.is_scanned,
        text_density=result.text_density,
        recommended_strategy=result.recommended_strategy,
        pages=[
            SamplePageOut(
                number=page.number,
                lines=[
                    SampleLineOut(top=line.top, x0=line.x0, x1=line.x1, text=line.text)
                    for line in page.lines
                ],
                column_candidates=[
                    ColumnCandidateOut(x=c.x, support=c.support, sample=list(c.sample))
                    for c in page.column_candidates
                ],
                ruling_lines=RulingLinesOut(
                    vertical=list(page.ruling_lines["vertical"]),
                    horizontal=list(page.ruling_lines["horizontal"]),
                ),
            )
            for page in result.pages
        ],
    )
