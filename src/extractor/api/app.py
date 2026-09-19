"""FastAPI application factory."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response

from extractor.api.concurrency import ConcurrencyLimiter
from extractor.api.error_handlers import register_error_handlers
from extractor.api.logging import configure_logging, new_request_id, request_id_var
from extractor.api.routes import router
from extractor.config import Settings, get_settings
from extractor.observability.metrics import observe_request


def _endpoint_label(path: str) -> str:
    if path.startswith("/v1/extract"):
        return "/v1/extract"
    if path.startswith("/v1/sample"):
        return "/v1/sample"
    if path.startswith("/v1/version"):
        return "/v1/version"
    if path in {"/health", "/ready", "/metrics"}:
        return path
    return "other"


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build and configure the FastAPI application."""
    resolved = settings if settings is not None else get_settings()
    configure_logging(resolved.log_level)

    app = FastAPI(title="greenery-extractor", version="1.0.0")
    app.state.settings = resolved
    app.state.concurrency_limiter = ConcurrencyLimiter(resolved.max_concurrency)
    app.dependency_overrides[get_settings] = lambda: resolved

    register_error_handlers(app)
    app.include_router(router)

    @app.middleware("http")
    async def request_id_middleware(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        incoming = request.headers.get("X-Request-Id")
        request_id = incoming.strip() if incoming and incoming.strip() else new_request_id()
        token = request_id_var.set(request_id)
        try:
            response = await call_next(request)
            response.headers["X-Request-Id"] = request_id
            observe_request(
                endpoint=_endpoint_label(request.url.path),
                status=response.status_code,
            )
            return response
        finally:
            request_id_var.reset(token)

    return app


# ASGI entrypoint for uvicorn: extractor.api.app:app
app = create_app()
