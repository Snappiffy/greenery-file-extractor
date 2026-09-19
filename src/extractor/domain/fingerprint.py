"""Fingerprint del layout: estable ante datos, sensible ante estructura."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from typing import Literal

from pydantic import BaseModel, ConfigDict

from extractor.domain.layout import find_column_candidates
from extractor.domain.models import Line, Page

ComponentName = Literal[
    "page_size",
    "rotation",
    "column_count",
    "boundaries",
    "header_text",
    "strategy",
]

_COMPONENT_ORDER: tuple[ComponentName, ...] = (
    "page_size",
    "rotation",
    "column_count",
    "boundaries",
    "header_text",
    "strategy",
)

_NON_ALPHA_RE = re.compile(r"[^a-z ]+")
_WHITESPACE_RE = re.compile(r"\s+")


class FingerprintComponents(BaseModel):
    """Componentes estructurales del fingerprint (no el contenido)."""

    model_config = ConfigDict(frozen=True)

    page_size: str
    rotation: str
    column_count: str
    boundaries: str
    header_text: str
    strategy: str

    def to_lines(self) -> list[str]:
        return [
            f"page_size:{self.page_size}",
            f"rotation:{self.rotation}",
            f"columns:{self.column_count}",
            f"boundaries:{self.boundaries}",
            f"header:{self.header_text}",
            f"strategy:{self.strategy}",
        ]

    def as_dict(self) -> dict[str, str]:
        return {
            "page_size": self.page_size,
            "rotation": self.rotation,
            "column_count": self.column_count,
            "boundaries": self.boundaries,
            "header_text": self.header_text,
            "strategy": self.strategy,
        }


class FingerprintResult(BaseModel):
    """Hash + componentes para comparación y diagnóstico."""

    model_config = ConfigDict(frozen=True)

    fingerprint: str
    components: FingerprintComponents


def normalize_header_text(text: str) -> str:
    """Normaliza texto de cabecera para el fingerprint (elimina dígitos)."""
    result = unicodedata.normalize("NFKC", text).casefold()
    result = "".join(ch for ch in result if not ch.isdigit())
    result = _NON_ALPHA_RE.sub("", result)
    result = _WHITESPACE_RE.sub(" ", result).strip()
    return result


def hash_components(components: FingerprintComponents) -> str:
    digest = hashlib.sha256("\n".join(components.to_lines()).encode("utf-8")).hexdigest()
    return f"sha256:{digest[:32]}"


def compare_components(
    expected: FingerprintComponents,
    actual: FingerprintComponents,
) -> list[ComponentName]:
    """Devuelve los nombres de componentes que difieren, en orden canónico."""
    changed: list[ComponentName] = []
    expected_map = expected.as_dict()
    actual_map = actual.as_dict()
    for name in _COMPONENT_ORDER:
        if expected_map[name] != actual_map[name]:
            changed.append(name)
    return changed


def locate_header_text(
    lines: list[Line],
    *,
    anchor_text: str | None = None,
    match: Literal["contains", "exact", "regex"] = "contains",
) -> str:
    """Localiza la línea de cabecera en la página 1."""
    if not lines:
        return ""

    if anchor_text:
        for line in lines:
            haystack = line.text
            if match == "exact" and haystack == anchor_text:
                return haystack
            if match == "contains" and anchor_text in haystack:
                return haystack
            if match == "regex" and re.search(anchor_text, haystack) is not None:
                return haystack

    for line in lines:
        if len(line.words) >= 3:
            return line.text
    return lines[0].text


def build_components(
    page: Page,
    lines: list[Line],
    *,
    header_anchor_text: str | None = None,
    header_match: Literal["contains", "exact", "regex"] = "contains",
) -> FingerprintComponents:
    """Construye los componentes del fingerprint a partir de la página 1."""
    candidates = find_column_candidates(page.words, line_count=max(len(lines), 1))
    boundaries = ",".join(f"{int(round(c.x / 5) * 5)}" for c in candidates)
    header = normalize_header_text(
        locate_header_text(
            lines,
            anchor_text=header_anchor_text,
            match=header_match,
        )
    )
    strategy = "columns" if len(candidates) >= 2 else "regex"
    return FingerprintComponents(
        page_size=f"{page.width:.0f}x{page.height:.0f}",
        rotation=str(page.rotation),
        column_count=str(len(candidates)),
        boundaries=boundaries,
        header_text=header,
        strategy=strategy,
    )


def compute_fingerprint(
    page: Page,
    lines: list[Line],
    *,
    header_anchor_text: str | None = None,
    header_match: Literal["contains", "exact", "regex"] = "contains",
) -> FingerprintResult:
    """Calcula fingerprint y componentes del layout de la página 1."""
    components = build_components(
        page,
        lines,
        header_anchor_text=header_anchor_text,
        header_match=header_match,
    )
    return FingerprintResult(
        fingerprint=hash_components(components),
        components=components,
    )
