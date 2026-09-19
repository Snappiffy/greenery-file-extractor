"""Tests de aceptación M7: OCR."""

from __future__ import annotations

import base64
import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from tests.fixtures.ocr import _generate as gen

from extractor.api.app import create_app
from extractor.config import Settings

OCR_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "ocr"
TESSERACT = shutil.which("tesseract")


@pytest.fixture(scope="module", autouse=True)
def _fixtures() -> None:
    gen.main()


def _has_tesseract() -> bool:
    return TESSERACT is not None


requires_tesseract = pytest.mark.skipif(
    not _has_tesseract(),
    reason="tesseract binary not available",
)


@pytest.fixture
def ocr_settings() -> Settings:
    assert TESSERACT is not None
    return Settings(
        extractor_shared_secret="test-secret-with-at-least-32-chars!",
        fetch_allowed_hosts=["fixtures.local"],
        environment="development",
        ocr_enabled=True,
        tesseract_cmd=TESSERACT,
    )


@pytest.fixture
def ocr_client(ocr_settings: Settings) -> TestClient:
    app = create_app(ocr_settings)
    return TestClient(app)


@pytest.fixture
def ocr_auth(ocr_settings: Settings) -> dict[str, str]:
    return {"Authorization": f"Bearer {ocr_settings.extractor_shared_secret}"}


def _body(*, ocr: str) -> dict:
    pdf = (OCR_ROOT / "scanned.pdf").read_bytes()
    profile = json.loads((OCR_ROOT / "profile.json").read_text(encoding="utf-8"))
    return {
        "document": {
            "inline_base64": base64.b64encode(pdf).decode("ascii"),
            "content_type": "application/pdf",
            "filename": "scanned.pdf",
        },
        "profile": profile,
        "options": {
            "ocr": ocr,
            "fail_on_fingerprint_mismatch": False,
        },
    }


@pytest.mark.ocr
@requires_tesseract
def test_scanned_pdf_uses_ocr_and_reports_confidence(
    ocr_client: TestClient, ocr_auth: dict[str, str]
) -> None:
    response = ocr_client.post("/v1/extract", headers=ocr_auth, json=_body(ocr="auto"))
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["diagnostics"]["ocr_used"] is True
    assert payload["diagnostics"]["ocr_mean_confidence"] is not None
    assert payload["diagnostics"]["ocr_mean_confidence"] > 0
    assert len(payload["rows"]) >= 1
    assert payload["rows"][0]["parsed"]["plant_name"]


@pytest.mark.ocr
def test_scanned_pdf_with_ocr_never_is_unreadable(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """Sin OCR (never) un escaneado es ilegible — no requiere binario."""
    response = client.post("/v1/extract", headers=auth_headers, json=_body(ocr="never"))
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "DOCUMENT_UNREADABLE"


@pytest.mark.ocr
def test_ready_degraded_when_ocr_enabled_without_binary() -> None:
    settings = Settings(
        extractor_shared_secret="test-secret-with-at-least-32-chars!",
        fetch_allowed_hosts=["fixtures.local"],
        environment="development",
        ocr_enabled=True,
        tesseract_cmd="tesseract-binary-that-does-not-exist",
    )
    app = create_app(settings)
    with TestClient(app) as test_client:
        response = test_client.get(
            "/ready",
            headers={"Authorization": f"Bearer {settings.extractor_shared_secret}"},
        )
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "degraded"
    assert body["checks"]["tesseract"] == "fail"


@pytest.mark.ocr
def test_ocr_marker_skips_cleanly_without_binary() -> None:
    """Contrato M7: los tests ocr se saltan si no hay tesseract."""
    if _has_tesseract():
        pytest.skip("tesseract is installed; skip-path covered by skipif elsewhere")
    assert TESSERACT is None
