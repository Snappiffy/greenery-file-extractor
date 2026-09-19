"""Tests de aceptación M6: fingerprint como guarda operativa."""

from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from tests.fixtures.golden import _generate as gen_golden
from tests.fixtures.m2 import _generate as gen_m2

from extractor.adapters.readers.pymupdf_reader import PyMuPdfReader
from extractor.domain.fingerprint import compute_fingerprint
from extractor.engine.lines import group_words_into_lines

GOLDEN_PDF = Path("tests/fixtures/golden/acme-single/catalog.pdf")
GOLDEN_PROFILE = Path("tests/fixtures/golden/acme-single/profile.json")
M2 = Path("tests/fixtures/m2")
HEADER_ANCHOR = "BOTANICAL NAME"


@pytest.fixture(scope="module", autouse=True)
def _fixtures() -> None:
    gen_golden.main()
    gen_m2.main()


def _fingerprint_payload(path: Path) -> tuple[str, dict[str, str]]:
    pages = PyMuPdfReader().read(path.read_bytes())
    page = pages[0]
    lines = group_words_into_lines(page.words, page=page.number)
    result = compute_fingerprint(page, lines, header_anchor_text=HEADER_ANCHOR)
    return result.fingerprint, result.components.as_dict()


def _auth(settings) -> dict[str, str]:  # type: ignore[no-untyped-def]
    return {"Authorization": f"Bearer {settings.extractor_shared_secret}"}


def _columns_profile_for_m2() -> dict:
    """Perfil columns compatible con los PDFs de layout M2."""
    return {
        "schema_version": 1,
        "version": 1,
        "document": {"kind": "pdf", "pages": "all"},
        "table": {
            "strategy": "columns",
            "column_boundaries": [52.0, 268.0, 372.0, 468.0, 560.0],
            "boundary_tolerance": 8.0,
            "header_anchor": {
                "text": "BOTANICAL NAME",
                "match": "contains",
                "on_every_page": True,
                "offset_lines": 0,
            },
            "stop_patterns": [],
            "row_tolerance": 3.0,
            "multiline": {"enabled": False},
        },
        "columns": [
            {"role": "plant_name", "index": 0, "required": True},
            {"role": "size", "index": 1, "required": True},
            {"role": "price", "index": 2},
            {"role": "quantity", "index": 3},
        ],
        "parsing": {
            "price": {"strip": ["$", "USD", "ea", "/ea", "each"]},
            "size": {
                "patterns": [
                    {
                        "regex": r'(?P<v>\d+(?:\.\d+)?)\s*"',
                        "unit": "in",
                        "dimension": "pot_diameter",
                    }
                ]
            },
        },
    }


def test_layout_changed_returns_409_with_changed(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    base_fp, base_components = _fingerprint_payload(M2 / "layout_base.pdf")
    shifted = (M2 / "layout_shifted_price.pdf").read_bytes()
    profile = _columns_profile_for_m2()
    profile["layout_fingerprint"] = base_fp
    profile["layout_components"] = base_components

    body = {
        "document": {
            "inline_base64": base64.b64encode(shifted).decode("ascii"),
            "content_type": "application/pdf",
            "filename": "shifted.pdf",
        },
        "profile": profile,
        "options": {"fail_on_fingerprint_mismatch": True},
    }
    response = client.post("/v1/extract", headers=auth_headers, json=body)
    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "FINGERPRINT_MISMATCH"
    assert error["detail"]["changed"] == ["boundaries"]
    assert "actual_components" in error["detail"]
    assert error["detail"]["expected"] == base_fp


def test_layout_changed_with_fail_off_returns_200_unmatched(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    base_fp, base_components = _fingerprint_payload(M2 / "layout_base.pdf")
    shifted = (M2 / "layout_shifted_price.pdf").read_bytes()
    profile = _columns_profile_for_m2()
    profile["layout_fingerprint"] = base_fp
    profile["layout_components"] = base_components

    body = {
        "document": {
            "inline_base64": base64.b64encode(shifted).decode("ascii"),
            "content_type": "application/pdf",
            "filename": "shifted.pdf",
        },
        "profile": profile,
        "options": {"fail_on_fingerprint_mismatch": False},
    }
    response = client.post("/v1/extract", headers=auth_headers, json=body)
    assert response.status_code == 200
    payload = response.json()
    assert payload["layout"]["matched"] is False
    assert payload["layout"]["expected_fingerprint"] == base_fp
    assert payload["layout"]["fingerprint"] != base_fp
    assert len(payload["rows"]) >= 1


def test_shifted_boundaries_emit_cross_boundary_warning(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    profile = json.loads(GOLDEN_PROFILE.read_text(encoding="utf-8"))
    # Desfase deliberado de 20 pt respecto al layout real.
    profile["table"]["column_boundaries"] = [
        b + 20.0 for b in profile["table"]["column_boundaries"]
    ]
    profile["table"]["boundary_tolerance"] = 4.0

    body = {
        "document": {
            "inline_base64": base64.b64encode(GOLDEN_PDF.read_bytes()).decode("ascii"),
            "content_type": "application/pdf",
            "filename": "catalog.pdf",
        },
        "profile": profile,
        "options": {"fail_on_fingerprint_mismatch": False},
    }
    response = client.post("/v1/extract", headers=auth_headers, json=body)
    assert response.status_code == 200
    payload = response.json()
    warnings = payload["diagnostics"]["warnings"]
    assert warnings, "expected aggregated TEXT_CROSSES_BOUNDARY warning"
    assert any("column_boundaries" in item for item in warnings)
    assert payload["diagnostics"]["issues_by_code"].get("TEXT_CROSSES_BOUNDARY", 0) > 0


def test_fingerprint_mismatch_increments_metric(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    before = client.get("/metrics").text
    before_count = _metric_value(before, "extractor_fingerprint_mismatch_total")

    base_fp, base_components = _fingerprint_payload(M2 / "layout_base.pdf")
    shifted = (M2 / "layout_shifted_price.pdf").read_bytes()
    profile = _columns_profile_for_m2()
    profile["layout_fingerprint"] = base_fp
    profile["layout_components"] = base_components

    body = {
        "document": {
            "inline_base64": base64.b64encode(shifted).decode("ascii"),
            "content_type": "application/pdf",
        },
        "profile": profile,
        "options": {"fail_on_fingerprint_mismatch": True},
    }
    assert client.post("/v1/extract", headers=auth_headers, json=body).status_code == 409

    after = client.get("/metrics").text
    after_count = _metric_value(after, "extractor_fingerprint_mismatch_total")
    assert after_count == before_count + 1.0


def _metric_value(metrics_text: str, name: str) -> float:
    for line in metrics_text.splitlines():
        if line.startswith("#"):
            continue
        if line.startswith(name + " ") or line.startswith(name + "{"):
            return float(line.rsplit(" ", 1)[-1])
    return 0.0
