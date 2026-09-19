"""Métricas Prometheus del extractor (docs/08)."""

from __future__ import annotations

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

REQUESTS_TOTAL = Counter(
    "extractor_requests_total",
    "HTTP requests handled by the extractor",
    ["endpoint", "status"],
)

DURATION_SECONDS = Histogram(
    "extractor_duration_seconds",
    "Request duration in seconds",
    ["endpoint", "strategy", "ocr"],
)

ROWS_EXTRACTED = Histogram(
    "extractor_rows_extracted",
    "Rows extracted per successful extract request",
    ["strategy"],
)

ISSUES_TOTAL = Counter(
    "extractor_issues_total",
    "Extraction issues by code and severity",
    ["code", "severity"],
)

FINGERPRINT_MISMATCH_TOTAL = Counter(
    "extractor_fingerprint_mismatch_total",
    "Document layout fingerprint did not match the profile",
)

CONCURRENCY_REJECTED_TOTAL = Counter(
    "extractor_concurrency_rejected_total",
    "Requests rejected because MAX_CONCURRENCY was saturated",
)


def inc_fingerprint_mismatch() -> None:
    """Incrementa el contador de mismatch de fingerprint."""
    FINGERPRINT_MISMATCH_TOTAL.inc()


def inc_concurrency_rejected() -> None:
    """Incrementa rechazos por semáforo de concurrencia."""
    CONCURRENCY_REJECTED_TOTAL.inc()


def observe_request(*, endpoint: str, status: int) -> None:
    REQUESTS_TOTAL.labels(endpoint=endpoint, status=str(status)).inc()


def observe_duration(
    *,
    endpoint: str,
    strategy: str,
    ocr: str,
    seconds: float,
) -> None:
    DURATION_SECONDS.labels(endpoint=endpoint, strategy=strategy, ocr=ocr).observe(seconds)


def observe_rows_extracted(*, strategy: str, rows: int) -> None:
    ROWS_EXTRACTED.labels(strategy=strategy).observe(rows)


def observe_issue(*, code: str, severity: str, count: int = 1) -> None:
    if count <= 0:
        return
    ISSUES_TOTAL.labels(code=code, severity=severity).inc(count)


def render_metrics() -> tuple[bytes, str]:
    """Payload y content-type de /metrics."""
    return generate_latest(), CONTENT_TYPE_LATEST
