"""Pytest fixtures compartidos."""

from __future__ import annotations

import os
import socket
from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Debe ejecutarse antes de importar la app (Settings lee el entorno al cargar el módulo).
os.environ.setdefault(
    "EXTRACTOR_SHARED_SECRET",
    "test-secret-with-at-least-32-chars!",
)
os.environ.setdefault("FETCH_ALLOWED_HOSTS", "fixtures.local")
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("OCR_ENABLED", "false")

from extractor.api.app import create_app
from extractor.config import Settings, clear_settings_cache


@pytest.fixture(autouse=True)
def no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bloquea cualquier intento de abrir una conexión de red en la suite."""

    def deny(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("un test intentó abrir una conexión de red")

    monkeypatch.setattr(socket.socket, "connect", deny)


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> Iterator[None]:
    clear_settings_cache()
    yield
    clear_settings_cache()


@pytest.fixture
def settings() -> Settings:
    return Settings(
        extractor_shared_secret="test-secret-with-at-least-32-chars!",
        fetch_allowed_hosts=["fixtures.local"],
        environment="development",
        ocr_enabled=False,
    )


@pytest.fixture
def app(settings: Settings) -> FastAPI:
    return create_app(settings)


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def auth_headers(settings: Settings) -> dict[str, str]:
    return {"Authorization": f"Bearer {settings.extractor_shared_secret}"}
