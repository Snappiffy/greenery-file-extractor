"""Tests de aceptación M8: métricas, concurrencia, timeout, fuga de logs."""

from __future__ import annotations

import base64
import json
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from tests.fixtures.golden import _generate as gen
from tests.golden.helpers import GOLDEN_ROOT, run_golden

from extractor.api.app import create_app
from extractor.api.logging import JsonFormatter
from extractor.config import Settings

GOLDEN_PDF = Path("tests/fixtures/golden/acme-single/catalog.pdf")
GOLDEN_PROFILE = Path("tests/fixtures/golden/acme-single/profile.json")

REQUIRED_METRICS = (
    "extractor_requests_total",
    "extractor_duration_seconds",
    "extractor_rows_extracted",
    "extractor_issues_total",
    "extractor_fingerprint_mismatch_total",
    "extractor_concurrency_rejected_total",
)


@pytest.fixture(scope="module", autouse=True)
def _fixtures() -> None:
    gen.main()


def _settings(**overrides: object) -> Settings:
    base: dict[str, object] = {
        "extractor_shared_secret": "test-secret-with-at-least-32-chars!",
        "fetch_allowed_hosts": ["fixtures.local"],
        "environment": "development",
        "ocr_enabled": False,
        "max_concurrency": 4,
        "extraction_timeout_seconds": 120,
    }
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


def _auth(settings: Settings) -> dict[str, str]:
    return {"Authorization": f"Bearer {settings.extractor_shared_secret}"}


def _extract_body() -> dict:
    profile = json.loads(GOLDEN_PROFILE.read_text(encoding="utf-8"))
    return {
        "document": {
            "inline_base64": base64.b64encode(GOLDEN_PDF.read_bytes()).decode("ascii"),
            "content_type": "application/pdf",
            "filename": "catalog.pdf",
        },
        "profile": profile,
        "options": {"fail_on_fingerprint_mismatch": False},
    }


def test_metrics_exposes_all_six_names(client: TestClient) -> None:
    # Dispara una petición para que existan series etiquetadas.
    client.get("/health")
    text = client.get("/metrics").text
    for name in REQUIRED_METRICS:
        assert name in text, f"missing metric {name}"


def test_concurrency_limit_returns_503_with_retry_after() -> None:
    settings = _settings(max_concurrency=1, extraction_timeout_seconds=30)
    app = create_app(settings)
    started = threading.Event()
    release = threading.Event()

    import extractor.application.extract_document as extract_mod

    real = extract_mod.extract_document

    def blocked(*args: object, **kwargs: object) -> object:
        started.set()
        assert release.wait(timeout=5)
        return real(*args, **kwargs)

    with TestClient(app) as client:
        # Parche en el módulo usado por routes
        import extractor.api.routes as routes_mod

        original = routes_mod.extract_document
        routes_mod.extract_document = blocked  # type: ignore[assignment]
        try:
            body = _extract_body()
            headers = _auth(settings)

            def first() -> object:
                return client.post("/v1/extract", headers=headers, json=body)

            def second() -> object:
                assert started.wait(timeout=5)
                return client.post("/v1/extract", headers=headers, json=body)

            with ThreadPoolExecutor(max_workers=2) as pool:
                fut1 = pool.submit(first)
                fut2 = pool.submit(second)
                # Espera a que la segunda haya respondido antes de liberar la primera.
                second_response = fut2.result(timeout=10)
                release.set()
                first_response = fut1.result(timeout=10)
        finally:
            routes_mod.extract_document = original  # type: ignore[assignment]

    statuses = sorted([first_response.status_code, second_response.status_code])
    assert statuses == [200, 503]
    rejected = first_response if first_response.status_code == 503 else second_response
    assert rejected.headers.get("Retry-After") is not None
    assert rejected.json()["error"]["code"] == "CONCURRENCY_LIMIT"


def test_extraction_timeout_returns_504_and_process_stays_healthy() -> None:
    settings = _settings(extraction_timeout_seconds=1, max_concurrency=2)
    app = create_app(settings)

    import extractor.api.routes as routes_mod

    def slow(*_args: object, **_kwargs: object) -> object:
        time.sleep(3)
        raise AssertionError("should have timed out")

    original = routes_mod.extract_document
    routes_mod.extract_document = slow  # type: ignore[assignment]
    try:
        with TestClient(app) as client:
            response = client.post(
                "/v1/extract",
                headers=_auth(settings),
                json=_extract_body(),
            )
            assert response.status_code == 504
            assert response.json()["error"]["code"] == "EXTRACTION_TIMEOUT"
            health = client.get("/health")
            assert health.status_code == 200
            assert health.json()["status"] == "ok"
    finally:
        routes_mod.extract_document = original  # type: ignore[assignment]


def test_logs_do_not_leak_fixture_strings(caplog: pytest.LogCaptureFixture) -> None:
    """Durante el golden set no debe aparecer texto de filas/precios en logs."""
    forbidden = _fixture_sensitive_strings()
    assert forbidden, "expected sensitive fixture strings"

    handler = logging.Handler()
    records: list[str] = []

    class _Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            formatter = JsonFormatter()
            records.append(formatter.format(record))

    capture = _Capture()
    root = logging.getLogger()
    root.addHandler(capture)
    try:
        with caplog.at_level(logging.INFO):
            for folder in sorted(
                path
                for path in GOLDEN_ROOT.iterdir()
                if path.is_dir() and (path / "catalog.pdf").exists()
            ):
                # Dispara el camino de aplicación (logs de extract vía API serían
                # más fieles; aquí cubrimos el golden + logger extractor).
                run_golden(folder)
                logging.getLogger("extractor.api").info(
                    "extract.completed",
                    extra={
                        "extra_fields": {
                            "grower_id": "test-grower",
                            "profile_version": 1,
                            "content_type": "application/pdf",
                            "pages": 1,
                            "rows_extracted": 1,
                            "rows_with_errors": 0,
                            "strategy": "columns",
                            "ocr_used": False,
                            "duration_ms": 1,
                        }
                    },
                )
    finally:
        root.removeHandler(capture)
        del handler

    blob = "\n".join(records)
    leaks = sorted(token for token in forbidden if token in blob)
    assert leaks == [], f"log leak detected: {leaks[:10]}"


def _fixture_sensitive_strings() -> set[str]:
    tokens: set[str] = set()
    for folder in GOLDEN_ROOT.iterdir():
        expected = folder / "catalog.expected.json"
        if not expected.exists():
            continue
        payload = json.loads(expected.read_text(encoding="utf-8"))
        for row in payload.get("rows", []):
            for value in (row.get("raw") or {}).values():
                text = str(value).strip()
                if len(text) >= 4:
                    tokens.add(text)
            plant = (row.get("parsed") or {}).get("plant_name")
            if isinstance(plant, str) and len(plant) >= 4:
                tokens.add(plant)
            price = (row.get("parsed") or {}).get("price")
            if isinstance(price, str) and len(price) >= 4:
                tokens.add(price)
    return tokens
