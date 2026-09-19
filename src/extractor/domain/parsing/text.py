"""Normalización de texto según el perfil."""

from __future__ import annotations

import re
import unicodedata

from extractor.domain.profile import TextConfig

_SOFT_HYPHEN = "\u00ad"
_WHITESPACE_RE = re.compile(r"\s+")


def normalize_text(text: str, cfg: TextConfig | None = None) -> str:
    """Aplica las reglas de parsing.text. Función pura e idempotente."""
    config = cfg if cfg is not None else TextConfig()
    result = text

    if config.normalize_unicode == "NFKC":
        result = unicodedata.normalize("NFKC", result)

    if config.drop_soft_hyphens:
        result = result.replace(_SOFT_HYPHEN, "")

    if config.trim:
        result = result.strip()

    if config.collapse_whitespace:
        result = _WHITESPACE_RE.sub(" ", result)
        if config.trim:
            result = result.strip()

    return result
