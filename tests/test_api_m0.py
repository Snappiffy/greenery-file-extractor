"""Tests de los endpoints de M0."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_health_ok(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_does_not_require_auth(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200


def test_ready_requires_auth(client: TestClient) -> None:
    response = client.get("/ready")
    assert response.status_code == 401
    body = response.json()
    assert body["error"]["code"] == "UNAUTHORIZED"


def test_ready_ok(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get("/ready", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["checks"]["pymupdf"] == "ok"
    assert body["engine_version"] == "1.0.0"
    assert "tesseract" not in body["checks"]


def test_version(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get("/v1/version", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["engine_version"] == "1.0.0"
    assert body["profile_schema_version"] == 1
    assert body["supported_strategies"] == ["columns", "ruling", "regex"]
    assert "application/pdf" in body["supported_content_types"]


def test_extract_without_bearer_returns_401(client: TestClient) -> None:
    response = client.post("/v1/extract", json={})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_extract_with_bearer_invalid_body_returns_400(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = client.post("/v1/extract", headers=auth_headers, json={})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_REQUEST"


def test_extract_with_wrong_bearer_returns_401(client: TestClient) -> None:
    response = client.post(
        "/v1/extract",
        headers={"Authorization": "Bearer wrong-secret-that-is-long-enough!!"},
        json={},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_request_id_echoed(client: TestClient) -> None:
    response = client.get("/health", headers={"X-Request-Id": "req-abc-123"})
    assert response.headers["X-Request-Id"] == "req-abc-123"


def test_request_id_generated_when_absent(client: TestClient) -> None:
    response = client.get("/health")
    assert "X-Request-Id" in response.headers
    assert len(response.headers["X-Request-Id"]) > 0
