"""DTOs HTTP de petición y respuesta."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DocumentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str | None = None
    inline_base64: str | None = None
    content_type: str
    filename: str | None = None
    sha256: str | None = None

    @model_validator(mode="after")
    def _xor_source(self) -> DocumentRequest:
        has_url = self.url is not None and self.url != ""
        has_inline = self.inline_base64 is not None and self.inline_base64 != ""
        if has_url == has_inline:
            raise ValueError("Provide exactly one of url or inline_base64")
        return self


class ExtractOptionsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ocr: Literal["never", "auto", "force"] = "auto"
    max_pages: int = 200
    include_bbox: bool = True
    include_raw_words: bool = False
    fail_on_fingerprint_mismatch: bool = True


class ExtractRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document: DocumentRequest
    profile: dict[str, Any]
    options: ExtractOptionsRequest = Field(default_factory=ExtractOptionsRequest)


class SizeOut(BaseModel):
    magnitude: str
    unit: str
    dimension: str
    raw: str


class ParsedOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plant_name: str | None
    size: SizeOut | None
    price: str | None
    quantity: int | None
    availability: bool | None
    grower_code: str | None
    notes: str | None


class IssueOut(BaseModel):
    code: str
    severity: str
    field: str | None = None
    detail: str | dict[str, Any] | None = None


class BBoxOut(BaseModel):
    page: int
    x0: float
    top: float
    x1: float
    bottom: float


class RowOut(BaseModel):
    row_index: int
    page: int
    source_lines: list[int]
    raw: dict[str, str]
    text: dict[str, str]
    parsed: ParsedOut
    issues: list[IssueOut]
    bbox: BBoxOut | None = None


class LayoutOut(BaseModel):
    fingerprint: str
    expected_fingerprint: str | None
    matched: bool
    page_count: int
    pages_processed: int
    page_geometry: dict[str, float | int]


class DiagnosticsOut(BaseModel):
    rows_extracted: int
    rows_dropped: int
    rows_with_errors: int
    rows_with_warnings: int
    issues_by_code: dict[str, int]
    dropped_by_reason: dict[str, int]
    pages_processed: int = 0
    pages_skipped: list[int] = Field(default_factory=list)
    ocr_used: bool
    ocr_mean_confidence: float | None
    strategy_used: str | None
    duration_ms: int
    warnings: list[str] = Field(default_factory=list)
    effective_profile: dict[str, Any] | None = None


class ExtractResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    engine_version: str
    profile_version: int
    layout: LayoutOut
    rows: list[RowOut]
    diagnostics: DiagnosticsOut


class SampleOptionsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pages: list[int] = Field(default_factory=lambda: [1])
    max_lines_per_page: int = 120
    ocr: Literal["never", "auto", "force"] = "auto"


class SampleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document: DocumentRequest
    options: SampleOptionsRequest = Field(default_factory=SampleOptionsRequest)


class ColumnCandidateOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    x: float
    support: int
    sample: list[str] = Field(default_factory=list)


class SampleLineOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    top: float
    x0: float
    x1: float
    text: str


class RulingLinesOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vertical: list[float]
    horizontal: list[float]


class SamplePageOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    number: int
    lines: list[SampleLineOut]
    column_candidates: list[ColumnCandidateOut]
    ruling_lines: RulingLinesOut


class SampleResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    engine_version: str
    fingerprint: str
    page_count: int
    page_geometry: dict[str, float | int]
    is_scanned: bool
    text_density: float
    recommended_strategy: str
    pages: list[SamplePageOut]
