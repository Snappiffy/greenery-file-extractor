"""HTTP routes for the extractor service."""

from __future__ import annotations

import shutil
import subprocess
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from starlette import status

from extractor import ENGINE_VERSION, PROFILE_SCHEMA_VERSION
from extractor.adapters.fetch.http_fetcher import HttpFetcher
from extractor.adapters.readers.pymupdf_reader import PyMuPdfReader
from extractor.api.auth import require_bearer
from extractor.api.schemas import ExtractRequest, ExtractResponse
from extractor.api.serialize import serialize_extract_result
from extractor.application.extract_document import (
    DocumentInput,
    ExtractOptions,
    extract_document,
)
from extractor.config import Settings, get_settings
from extractor.domain.errors import InvalidProfileError
from extractor.domain.profile import Profile

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    """Liveness probe — no auth, no dependencies."""
    return {"status": "ok"}


@router.get("/ready", dependencies=[Depends(require_bearer)])
def ready(settings: Settings = Depends(get_settings)) -> JSONResponse:
    """Readiness probe — verifies runtime dependencies."""
    checks: dict[str, str] = {}

    try:
        import pymupdf  # noqa: F401

        checks["pymupdf"] = "ok"
    except Exception:
        checks["pymupdf"] = "fail"

    if settings.ocr_enabled:
        tesseract = shutil.which(settings.tesseract_cmd)
        if tesseract is None:
            checks["tesseract"] = "fail"
        else:
            try:
                completed = subprocess.run(
                    [settings.tesseract_cmd, "--version"],
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                checks["tesseract"] = "ok" if completed.returncode == 0 else "fail"
            except (OSError, subprocess.SubprocessError):
                checks["tesseract"] = "fail"

    degraded = any(value != "ok" for value in checks.values())
    body: dict[str, Any] = {
        "status": "degraded" if degraded else "ready",
        "checks": checks,
        "engine_version": ENGINE_VERSION,
    }
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE if degraded else status.HTTP_200_OK,
        content=body,
    )


@router.get("/v1/version", dependencies=[Depends(require_bearer)])
def version() -> dict[str, Any]:
    """Engine capabilities advertised to the worker."""
    return {
        "engine_version": ENGINE_VERSION,
        "profile_schema_version": PROFILE_SCHEMA_VERSION,
        "supported_strategies": ["columns", "ruling", "regex"],
        "supported_content_types": [
            "application/pdf",
            "image/png",
            "image/jpeg",
            "image/tiff",
        ],
    }


@router.post(
    "/v1/extract",
    dependencies=[Depends(require_bearer)],
    response_model=ExtractResponse,
)
def extract(
    body: ExtractRequest,
    settings: Settings = Depends(get_settings),
) -> ExtractResponse:
    """Extrae filas aplicando el perfil."""
    try:
        profile = Profile.from_payload(body.profile)
    except InvalidProfileError:
        raise
    except Exception as exc:
        raise InvalidProfileError(str(exc), detail={}) from exc

    fetcher = HttpFetcher(
        allowed_hosts=settings.fetch_allowed_hosts,
        timeout_seconds=float(settings.fetch_timeout_seconds),
        max_bytes=settings.max_document_bytes,
    )

    def reader_for(_content_type: str) -> PyMuPdfReader:
        return PyMuPdfReader()

    result = extract_document(
        document=DocumentInput(
            content_type=body.document.content_type,
            filename=body.document.filename,
            url=body.document.url,
            inline_base64=body.document.inline_base64,
            sha256=body.document.sha256,
            password=profile.document.password,
        ),
        profile=profile,
        options=ExtractOptions(
            ocr=body.options.ocr,
            max_pages=min(body.options.max_pages, settings.max_pages),
            include_bbox=body.options.include_bbox,
            include_raw_words=body.options.include_raw_words,
            fail_on_fingerprint_mismatch=body.options.fail_on_fingerprint_mismatch,
        ),
        fetcher=fetcher,
        reader_for=reader_for,
        engine_version=ENGINE_VERSION,
        max_document_bytes=settings.max_document_bytes,
    )
    return serialize_extract_result(result)
