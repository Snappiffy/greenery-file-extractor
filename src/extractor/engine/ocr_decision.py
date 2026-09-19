"""Decisión never / auto / force de OCR (docs/05 § Paso 4)."""

from __future__ import annotations

from typing import Literal

OcrMode = Literal["never", "auto", "force"]
OcrDecision = Literal["native", "ocr", "unreadable"]


def decide_ocr(
    *,
    content_type: str,
    density: float,
    mode: OcrMode,
    density_threshold: float,
) -> OcrDecision:
    """Devuelve cómo leer el documento: texto nativo, OCR o ilegible."""
    if content_type.startswith("image/"):
        return "ocr"

    if mode == "never":
        if density == 0.0:
            return "unreadable"
        return "native"

    if mode == "force":
        return "ocr"

    # auto
    if density < density_threshold:
        return "ocr"
    return "native"
