"""Métricas Prometheus del extractor."""

from __future__ import annotations

from prometheus_client import CONTENT_TYPE_LATEST, Counter, generate_latest

FINGERPRINT_MISMATCH_TOTAL = Counter(
    "extractor_fingerprint_mismatch_total",
    "Document layout fingerprint did not match the profile",
)


def inc_fingerprint_mismatch() -> None:
    """Incrementa el contador de mismatch de fingerprint."""
    FINGERPRINT_MISMATCH_TOTAL.inc()


def render_metrics() -> tuple[bytes, str]:
    """Payload y content-type de /metrics."""
    return generate_latest(), CONTENT_TYPE_LATEST
