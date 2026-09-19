"""Modelos de dominio de la extracción."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from extractor.domain.issues import Issue, IssueCode, Severity

SizeDimension = Literal["pot_diameter", "pot_volume", "plant_height", "spread"]


class Word(BaseModel):
    """Palabra con bounding box en puntos PostScript."""

    model_config = ConfigDict(frozen=True)

    text: str
    x0: float
    top: float
    x1: float
    bottom: float
    confidence: float | None = None


class Line(BaseModel):
    """Línea de palabras agrupadas por proximidad vertical."""

    model_config = ConfigDict(frozen=True)

    words: list[Word]
    top: float
    x0: float
    x1: float
    bottom: float
    page: int
    line_index: int

    @property
    def text(self) -> str:
        return " ".join(word.text for word in self.words)


class Cell(BaseModel):
    """Celda recortada de una fila."""

    model_config = ConfigDict(frozen=True)

    role: str
    raw: str
    index: int


class Size(BaseModel):
    """Tamaño tipado con dimensión explícita del perfil."""

    model_config = ConfigDict(frozen=True)

    magnitude: Decimal
    unit: str
    dimension: SizeDimension
    raw: str

    def to_serializable(self) -> dict[str, str]:
        return {
            "magnitude": format(self.magnitude, "f"),
            "unit": self.unit,
            "dimension": self.dimension,
            "raw": self.raw,
        }


class Page(BaseModel):
    """Página con geometría y palabras en orden determinista."""

    model_config = ConfigDict(frozen=True)

    number: int
    width: float
    height: float
    rotation: int = 0
    words: list[Word] = Field(default_factory=list)


class BBox(BaseModel):
    """Rectángulo de una fila en la página."""

    model_config = ConfigDict(frozen=True)

    page: int
    x0: float
    top: float
    x1: float
    bottom: float


class ParsedRow(BaseModel):
    """Valores tipados de una fila."""

    model_config = ConfigDict(frozen=True)

    plant_name: str | None = None
    size: Size | None = None
    price: Decimal | None = None
    quantity: int | None = None
    availability: bool | None = None
    grower_code: str | None = None
    notes: str | None = None


class Row(BaseModel):
    """Una unidad de producto leída del documento."""

    model_config = ConfigDict(frozen=True)

    row_index: int
    page: int
    source_lines: list[int]
    raw: dict[str, str]
    text: dict[str, str]
    parsed: ParsedRow
    issues: list[Issue] = Field(default_factory=list)
    bbox: BBox | None = None


class Diagnostics(BaseModel):
    """Juicio agregado sobre la calidad de la lectura."""

    model_config = ConfigDict(frozen=True)

    rows_extracted: int = 0
    rows_dropped: int = 0
    rows_with_errors: int = 0
    rows_with_warnings: int = 0
    issues_by_code: dict[str, int] = Field(default_factory=dict)
    dropped_by_reason: dict[str, int] = Field(default_factory=dict)
    pages_processed: int = 0
    pages_skipped: list[int] = Field(default_factory=list)
    ocr_used: bool = False
    ocr_mean_confidence: float | None = None
    strategy_used: str | None = None
    duration_ms: int = 0
    warnings: list[str] = Field(default_factory=list)
    effective_profile: dict[str, Any] | None = None


__all__ = [
    "BBox",
    "Cell",
    "Diagnostics",
    "Issue",
    "IssueCode",
    "Line",
    "Page",
    "ParsedRow",
    "Row",
    "Severity",
    "Size",
    "SizeDimension",
    "Word",
]
