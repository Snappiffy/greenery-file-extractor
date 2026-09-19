"""Helpers para golden tests."""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

from extractor.adapters.readers.pymupdf_reader import PyMuPdfReader
from extractor.api.serialize import serialize_extract_result
from extractor.application.extract_document import (
    DocumentInput,
    ExtractOptions,
    ExtractResult,
    extract_document,
)
from extractor.domain.profile import Profile

GOLDEN_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "golden"


class InlineOnlyFetcher:
    def fetch(self, url: str) -> bytes:
        raise AssertionError(f"unexpected fetch: {url}")


def golden_dirs() -> list[Path]:
    return sorted(
        path for path in GOLDEN_ROOT.iterdir() if path.is_dir() and (path / "catalog.pdf").exists()
    )


def run_golden(folder: Path) -> ExtractResult:
    pdf = (folder / "catalog.pdf").read_bytes()
    profile = Profile.from_payload(json.loads((folder / "profile.json").read_text()))
    return extract_document(
        document=DocumentInput(
            content_type="application/pdf",
            inline_base64=base64.b64encode(pdf).decode("ascii"),
            filename="catalog.pdf",
        ),
        profile=profile,
        options=ExtractOptions(include_bbox=True, fail_on_fingerprint_mismatch=False),
        fetcher=InlineOnlyFetcher(),
        reader_for=lambda _ct: PyMuPdfReader(),
    )


def canonical_payload(result: ExtractResult) -> dict[str, Any]:
    payload = serialize_extract_result(result).model_dump(mode="json")
    payload["diagnostics"]["duration_ms"] = 0
    return payload
