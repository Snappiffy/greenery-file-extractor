"""Tests de aceptación M4: POST /v1/sample."""

from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest

from extractor.adapters.readers.pymupdf_reader import PyMuPdfReader
from extractor.api.serialize import serialize_sample_result
from extractor.application.extract_document import DocumentInput
from extractor.application.sample_document import SampleOptions, sample_document
from extractor.domain.profile import Profile

GOLDEN_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "golden"
TOLERANCE_PT = 4.0
MAX_RESPONSE_BYTES = 200 * 1024


class InlineOnlyFetcher:
    def fetch(self, url: str) -> bytes:
        raise AssertionError(f"unexpected fetch: {url}")


def _golden_dirs() -> list[Path]:
    return sorted(
        path for path in GOLDEN_ROOT.iterdir() if path.is_dir() and (path / "catalog.pdf").exists()
    )


def _run_sample(folder: Path) -> object:
    pdf = (folder / "catalog.pdf").read_bytes()
    return sample_document(
        document=DocumentInput(
            content_type="application/pdf",
            inline_base64=base64.b64encode(pdf).decode("ascii"),
            filename="catalog.pdf",
        ),
        options=SampleOptions(pages=[1], max_lines_per_page=120),
        fetcher=InlineOnlyFetcher(),
        reader_for=lambda _ct: PyMuPdfReader(),
    )


@pytest.mark.parametrize("folder", _golden_dirs(), ids=lambda p: p.name)
def test_column_candidates_match_profile_boundaries(folder: Path) -> None:
    profile = Profile.from_payload(json.loads((folder / "profile.json").read_text()))
    boundaries = list(profile.table.column_boundaries)
    # El último límite es el margen derecho; no tiene texto anclado.
    left_edges = boundaries[:-1]

    result = _run_sample(folder)
    assert result.pages, "sample must return at least one page"
    candidates = result.pages[0].column_candidates
    assert len(candidates) >= 2

    for edge in left_edges:
        nearest = min(abs(candidate.x - edge) for candidate in candidates)
        assert nearest <= TOLERANCE_PT, f"{folder.name}: edge {edge} nearest delta {nearest}"


@pytest.mark.parametrize("folder", _golden_dirs(), ids=lambda p: p.name)
def test_recommended_strategy_is_columns(folder: Path) -> None:
    profile = Profile.from_payload(json.loads((folder / "profile.json").read_text()))
    assert profile.table.strategy == "columns"
    result = _run_sample(folder)
    assert result.recommended_strategy == "columns"


@pytest.mark.parametrize("folder", _golden_dirs(), ids=lambda p: p.name)
def test_sample_response_under_200kb(folder: Path) -> None:
    result = _run_sample(folder)
    payload = serialize_sample_result(result).model_dump(mode="json")
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    assert len(encoded) <= MAX_RESPONSE_BYTES


def test_sample_http_endpoint(client, auth_headers: dict[str, str]) -> None:
    folder = GOLDEN_ROOT / "acme-single"
    pdf = (folder / "catalog.pdf").read_bytes()
    response = client.post(
        "/v1/sample",
        headers=auth_headers,
        json={
            "document": {
                "content_type": "application/pdf",
                "inline_base64": base64.b64encode(pdf).decode("ascii"),
                "filename": "catalog.pdf",
            },
            "options": {"pages": [1], "max_lines_per_page": 120},
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["recommended_strategy"] == "columns"
    assert body["pages"][0]["column_candidates"]
    assert "ruling_lines" in body["pages"][0]
