"""Tests de códigos de error HTTP de docs/02 para /v1/extract."""

from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from tests.fixtures.golden import _generate as gen

GOLDEN_PDF = Path("tests/fixtures/golden/acme-single/catalog.pdf")
GOLDEN_PROFILE = Path("tests/fixtures/golden/acme-single/profile.json")


@pytest.fixture(scope="module", autouse=True)
def _fixtures() -> None:
    gen.main()


def _auth(settings) -> dict[str, str]:  # type: ignore[no-untyped-def]
    return {"Authorization": f"Bearer {settings.extractor_shared_secret}"}


def _inline_body(profile: dict, **doc_extra: object) -> dict:
    pdf = GOLDEN_PDF.read_bytes()
    document = {
        "inline_base64": base64.b64encode(pdf).decode("ascii"),
        "content_type": "application/pdf",
        "filename": "catalog.pdf",
    }
    document.update(doc_extra)
    return {
        "document": document,
        "profile": profile,
        "options": {"fail_on_fingerprint_mismatch": False},
    }


def test_invalid_profile(client: TestClient, auth_headers: dict[str, str]) -> None:
    profile = json.loads(GOLDEN_PROFILE.read_text())
    profile["columns"] = [
        {"role": "plant_name", "index": 0, "required": True},
        {"role": "plant_name", "index": 1, "required": True},
        {"role": "size", "index": 2, "required": True},
    ]
    response = client.post("/v1/extract", headers=auth_headers, json=_inline_body(profile))
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_PROFILE"


def test_invalid_request_both_sources(client: TestClient, auth_headers: dict[str, str]) -> None:
    profile = json.loads(GOLDEN_PROFILE.read_text())
    body = _inline_body(profile)
    body["document"]["url"] = "https://fixtures.local/x.pdf"
    response = client.post("/v1/extract", headers=auth_headers, json=body)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_REQUEST"


def test_unauthorized(client: TestClient) -> None:
    response = client.post("/v1/extract", json={})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_fingerprint_mismatch(client: TestClient, auth_headers: dict[str, str]) -> None:
    profile = json.loads(GOLDEN_PROFILE.read_text())
    profile["layout_fingerprint"] = "sha256:" + ("0" * 32)
    body = _inline_body(profile)
    body["options"] = {"fail_on_fingerprint_mismatch": True}
    response = client.post("/v1/extract", headers=auth_headers, json=body)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "FINGERPRINT_MISMATCH"


def test_document_too_large_max_pages(
    client: TestClient, auth_headers: dict[str, str], settings
) -> None:  # type: ignore[no-untyped-def]
    profile = json.loads(GOLDEN_PROFILE.read_text())
    body = _inline_body(profile)
    body["options"] = {"max_pages": 0, "fail_on_fingerprint_mismatch": False}
    # max_pages 0 with min() against settings — use 0 causes exceed if pages>0
    # Our code: if len(pages) > options.max_pages. With max_pages=0, always too large.
    response = client.post("/v1/extract", headers=auth_headers, json=body)
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "DOCUMENT_TOO_LARGE"


def test_unsupported_content_type(client: TestClient, auth_headers: dict[str, str]) -> None:
    profile = json.loads(GOLDEN_PROFILE.read_text())
    body = _inline_body(profile, content_type="text/plain")
    response = client.post("/v1/extract", headers=auth_headers, json=body)
    assert response.status_code == 415
    assert response.json()["error"]["code"] == "UNSUPPORTED_CONTENT_TYPE"


def test_document_unreadable(client: TestClient, auth_headers: dict[str, str]) -> None:
    profile = json.loads(GOLDEN_PROFILE.read_text())
    body = _inline_body(profile)
    body["document"]["inline_base64"] = base64.b64encode(b"not-a-pdf").decode()
    response = client.post("/v1/extract", headers=auth_headers, json=body)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "DOCUMENT_UNREADABLE"


def test_sha256_mismatch(client: TestClient, auth_headers: dict[str, str]) -> None:
    profile = json.loads(GOLDEN_PROFILE.read_text())
    body = _inline_body(profile, sha256="deadbeef")
    response = client.post("/v1/extract", headers=auth_headers, json=body)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "SHA256_MISMATCH"


def test_no_rows_found(client: TestClient, auth_headers: dict[str, str]) -> None:
    profile = json.loads(GOLDEN_PROFILE.read_text())
    # Empujar boundaries fuera de página → sin celdas útiles / filas filtradas
    profile["table"]["column_boundaries"] = [900.0, 910.0, 920.0, 930.0, 940.0]
    profile["filters"] = {
        "drop_rows_matching": {"plant_name": [".*"]},
        "min_plant_name_length": 3,
    }
    response = client.post("/v1/extract", headers=auth_headers, json=_inline_body(profile))
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "NO_ROWS_FOUND"


def test_source_fetch_failed(client: TestClient, auth_headers: dict[str, str]) -> None:
    from unittest.mock import patch

    import httpx

    profile = json.loads(GOLDEN_PROFILE.read_text())
    body = {
        "document": {
            "url": "https://fixtures.local/missing.pdf",
            "content_type": "application/pdf",
        },
        "profile": profile,
        "options": {"fail_on_fingerprint_mismatch": False},
    }
    transport = httpx.MockTransport(lambda _req: httpx.Response(404))
    mock_client = httpx.Client(transport=transport, follow_redirects=False)
    with (
        patch("extractor.adapters.fetch.http_fetcher.socket.getaddrinfo") as gai,
        patch("extractor.api.routes.HttpFetcher") as fetcher_cls,
    ):
        gai.return_value = [(0, 0, 0, "", ("1.2.3.4", 443))]

        def build_fetcher(**kwargs):  # type: ignore[no-untyped-def]
            kwargs = {**kwargs, "client": mock_client}
            from extractor.adapters.fetch.http_fetcher import HttpFetcher

            return HttpFetcher(**kwargs)

        fetcher_cls.side_effect = build_fetcher
        response = client.post("/v1/extract", headers=auth_headers, json=body)
    mock_client.close()
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "SOURCE_FETCH_FAILED"

    """Fila con precio ilegible: raw intacto, price null, issue; HTTP 200."""
    import pymupdf

    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)
    page.insert_text((52, 118), "BOTANICAL NAME", fontsize=10)
    page.insert_text((268, 118), "SIZE", fontsize=10)
    page.insert_text((372, 118), "PRICE", fontsize=10)
    page.insert_text((468, 118), "QTY", fontsize=10)
    page.insert_text((52, 140), "Ficus lyrata", fontsize=9)
    page.insert_text((268, 140), '10"', fontsize=9)
    page.insert_text((372, 140), "ASK", fontsize=9)
    page.insert_text((468, 140), "12", fontsize=9)
    pdf_bytes = doc.tobytes()
    doc.close()

    profile = json.loads(GOLDEN_PROFILE.read_text())
    body = {
        "document": {
            "inline_base64": base64.b64encode(pdf_bytes).decode(),
            "content_type": "application/pdf",
        },
        "profile": profile,
        "options": {"fail_on_fingerprint_mismatch": False},
    }
    response = client.post("/v1/extract", headers=auth_headers, json=body)
    assert response.status_code == 200
    row = response.json()["rows"][0]
    assert row["raw"]["price"] == "ASK"
    assert row["parsed"]["price"] is None
    assert any(i["code"] == "PRICE_UNPARSEABLE" for i in row["issues"])


def test_nulls_and_decimals_are_strings(client: TestClient, auth_headers: dict[str, str]) -> None:
    profile = json.loads(GOLDEN_PROFILE.read_text())
    response = client.post("/v1/extract", headers=auth_headers, json=_inline_body(profile))
    assert response.status_code == 200
    row = response.json()["rows"][0]
    parsed = row["parsed"]
    assert isinstance(parsed["price"], str)
    assert "grower_code" in parsed
    assert "notes" in parsed
    assert parsed["grower_code"] is None
    assert parsed["notes"] is None
