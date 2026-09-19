"""Ejecución acotada: semáforo + timeout de extracción."""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError

from extractor.api.concurrency import ConcurrencyLimiter
from extractor.domain.errors import ConcurrencyLimitError, ExtractionTimeoutError
from extractor.observability.metrics import inc_concurrency_rejected

DEFAULT_RETRY_AFTER_SECONDS = 5


def run_guarded[T](
    *,
    limiter: ConcurrencyLimiter,
    timeout_seconds: float,
    fn: Callable[[], T],
    retry_after_seconds: int = DEFAULT_RETRY_AFTER_SECONDS,
) -> T:
    """Ejecuta `fn` bajo el semáforo y con timeout efectivo."""
    if not limiter.try_acquire():
        inc_concurrency_rejected()
        raise ConcurrencyLimitError(
            "Too many concurrent extractions on this instance.",
            detail={"retry_after": retry_after_seconds, "max_concurrency": limiter.max_concurrency},
        )
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(fn)
            try:
                return future.result(timeout=timeout_seconds)
            except FuturesTimeoutError as exc:
                raise ExtractionTimeoutError(
                    "Extraction exceeded EXTRACTION_TIMEOUT_SECONDS.",
                    detail={"timeout_seconds": timeout_seconds},
                ) from exc
    finally:
        limiter.release()
