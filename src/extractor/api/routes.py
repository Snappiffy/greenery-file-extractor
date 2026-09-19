"""HTTP routes for the extractor service."""

from __future__ import annotations

import shutil
import subprocess
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse

from extractor import ENGINE_VERSION, PROFILE_SCHEMA_VERSION
from extractor.api.auth import require_bearer
from extractor.config import Settings, get_settings

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


@router.post("/v1/extract", dependencies=[Depends(require_bearer)])
def extract(_request: Request) -> None:
    """Extraction endpoint — implemented in a later milestone."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail={
            "error": {
                "code": "NOT_IMPLEMENTED",
                "message": "POST /v1/extract is not implemented yet.",
                "detail": {},
            }
        },
    )
