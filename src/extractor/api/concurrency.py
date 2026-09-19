"""Semáforo de concurrencia por proceso (MAX_CONCURRENCY)."""

from __future__ import annotations

import threading


class ConcurrencyLimiter:
    """Adquiere un slot sin bloquear; si no hay, la petición debe responder 503."""

    def __init__(self, max_concurrency: int) -> None:
        if max_concurrency < 1:
            msg = "max_concurrency must be >= 1"
            raise ValueError(msg)
        self._semaphore = threading.BoundedSemaphore(max_concurrency)
        self.max_concurrency = max_concurrency

    def try_acquire(self) -> bool:
        return self._semaphore.acquire(blocking=False)

    def release(self) -> None:
        self._semaphore.release()
