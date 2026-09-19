"""Domain → HTTP error translation. Único sitio que conoce códigos HTTP."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from extractor.domain.errors import (
    ConcurrencyLimitError,
    DocumentTooLargeError,
    DocumentUnreadableError,
    ExtractionTimeoutError,
    ExtractorError,
    FingerprintMismatchError,
    InvalidProfileError,
    InvalidRequestError,
    NoRowsFoundError,
    Sha256MismatchError,
    SourceFetchFailedError,
    UnsupportedContentTypeError,
)

_STATUS_BY_ERROR: dict[type[ExtractorError], int] = {
    InvalidProfileError: 400,
    InvalidRequestError: 400,
    FingerprintMismatchError: 409,
    DocumentTooLargeError: 413,
    UnsupportedContentTypeError: 415,
    DocumentUnreadableError: 422,
    Sha256MismatchError: 422,
    NoRowsFoundError: 422,
    SourceFetchFailedError: 502,
    ConcurrencyLimitError: 503,
    ExtractionTimeoutError: 504,
}


def _error_body(code: str, message: str, detail: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "detail": detail or {}}}


def register_error_handlers(app: FastAPI) -> None:
    """Attach global exception handlers to the FastAPI app."""

    @app.exception_handler(ExtractorError)
    async def domain_exception_handler(_request: Request, exc: ExtractorError) -> JSONResponse:
        status = 500
        for error_type, code in _STATUS_BY_ERROR.items():
            if isinstance(exc, error_type):
                status = code
                break
        headers: dict[str, str] | None = None
        if isinstance(exc, ConcurrencyLimitError):
            retry_after = exc.detail.get("retry_after", 5)
            headers = {"Retry-After": str(retry_after)}
        return JSONResponse(
            status_code=status,
            content=_error_body(exc.code, exc.message, exc.detail),
            headers=headers,
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        _request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        if isinstance(exc.detail, dict) and "error" in exc.detail:
            return JSONResponse(status_code=exc.status_code, content=exc.detail)
        code = "HTTP_ERROR"
        if exc.status_code == 401:
            code = "UNAUTHORIZED"
        elif exc.status_code == 501:
            code = "NOT_IMPLEMENTED"
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_body(code, str(exc.detail)),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        errors = []
        for err in exc.errors():
            cleaned = {key: value for key, value in err.items() if key != "ctx"}
            if "ctx" in err and isinstance(err["ctx"], dict):
                cleaned["ctx"] = {
                    key: (
                        str(value)
                        if not isinstance(value, str | int | float | bool | type(None))
                        else value
                    )
                    for key, value in err["ctx"].items()
                }
            errors.append(cleaned)
        return JSONResponse(
            status_code=400,
            content=_error_body(
                "INVALID_REQUEST",
                "Request validation failed.",
                {"errors": errors},
            ),
        )
