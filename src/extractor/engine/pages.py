"""Selección de páginas según el perfil."""

from __future__ import annotations

import re

from extractor.domain.models import Page
from extractor.domain.profile import DocumentConfig


def select_pages(pages: list[Page], document: DocumentConfig) -> tuple[list[Page], list[int]]:
    """Devuelve (páginas a procesar, números saltados)."""
    wanted = _wanted_numbers(document.pages, total=len(pages))
    selected: list[Page] = []
    skipped: list[int] = []
    for page in pages:
        if page.number not in wanted:
            skipped.append(page.number)
            continue
        if _should_skip_page(page, document.skip_pages_matching):
            skipped.append(page.number)
            continue
        selected.append(page)
    return selected, skipped


def _wanted_numbers(pages_spec: str | list[int], *, total: int) -> set[int]:
    if pages_spec == "all":
        return set(range(1, total + 1))
    if isinstance(pages_spec, list):
        return {int(n) for n in pages_spec}
    text = pages_spec.strip()
    if re.fullmatch(r"\d+-\d+", text):
        start_s, end_s = text.split("-", 1)
        start, end = int(start_s), int(end_s)
        return set(range(start, end + 1))
    if text.isdigit():
        return {int(text)}
    return set(range(1, total + 1))


def _should_skip_page(page: Page, patterns: list[str]) -> bool:
    if not patterns:
        return False
    # Usa el texto de las primeras líneas de la página.
    sample = " ".join(word.text for word in page.words[:40])
    return any(re.search(pattern, sample) is not None for pattern in patterns)
