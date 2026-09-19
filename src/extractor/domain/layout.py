"""Geometría de layout: candidatos de columna, densidad de texto."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from extractor.domain.models import Page, Word

POINTS_PER_INCH = 72.0
COLUMN_BUCKET_PT = 3.0
MIN_SUPPORT_RATIO = 0.15


class ColumnCandidate(BaseModel):
    """Candidato de columna detectado por histograma de x0."""

    model_config = ConfigDict(frozen=True)

    x: float
    support: int
    sample: list[str] = Field(default_factory=list)


def sort_words(words: list[Word]) -> list[Word]:
    """Orden determinista: (top, x0, text) redondeados a 1 decimal."""
    return sorted(
        words,
        key=lambda word: (round(word.top, 1), round(word.x0, 1), word.text),
    )


def find_column_candidates(
    words: list[Word],
    *,
    line_count: int,
    bucket_size: float = COLUMN_BUCKET_PT,
    min_support_ratio: float = MIN_SUPPORT_RATIO,
    sample_limit: int = 3,
) -> list[ColumnCandidate]:
    """Histograma de x0 en cubos de 3 pt; filtra por support ≥ 15% de las líneas."""
    if not words or line_count <= 0:
        return []

    buckets: dict[int, list[Word]] = {}
    for word in words:
        key = round(word.x0 / bucket_size)
        buckets.setdefault(key, []).append(word)

    threshold = max(1, int(line_count * min_support_ratio))
    candidates: list[ColumnCandidate] = []
    for key in sorted(buckets):
        bucket_words = buckets[key]
        support = len(bucket_words)
        if support < threshold:
            continue
        # Representante: media de x0 del cubo, redondeada a 1 decimal.
        xs = [word.x0 for word in bucket_words]
        x = round(sum(xs) / len(xs), 1)
        sample: list[str] = []
        for word in sort_words(bucket_words):
            if word.text not in sample:
                sample.append(word.text)
            if len(sample) >= sample_limit:
                break
        candidates.append(ColumnCandidate(x=x, support=support, sample=sample))
    return candidates


def text_density(pages: list[Page], *, max_pages: int = 3) -> float:
    """Caracteres nativos por pulgada² en las primeras páginas."""
    selected = pages[:max_pages]
    if not selected:
        return 0.0
    chars = sum(len(word.text) for page in selected for word in page.words)
    area = sum(
        (page.width / POINTS_PER_INCH) * (page.height / POINTS_PER_INCH) for page in selected
    )
    if area <= 0:
        return 0.0
    return chars / area


def is_scanned(pages: list[Page]) -> bool:
    """True si no hay capa de texto nativo (densidad cero).

    El umbral OCR_DENSITY_THRESHOLD decide si correr OCR en modo auto;
    no define is_scanned. Ver docs/02 (text_density 0.87 con is_scanned false).
    """
    return text_density(pages) == 0.0
