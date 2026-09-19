"""Excepciones de dominio. No conocen códigos HTTP."""

from __future__ import annotations

from typing import Any


class ExtractorError(Exception):
    """Error de dominio base del extractor."""

    code: str = "EXTRACTOR_ERROR"

    def __init__(
        self,
        message: str,
        *,
        detail: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.detail: dict[str, Any] = detail or {}


class InvalidProfileError(ExtractorError):
    """El perfil no valida contra el esquema o es semánticamente incoherente."""

    code = "INVALID_PROFILE"


class DocumentUnreadableError(ExtractorError):
    """El documento no se puede abrir o no contiene páginas legibles."""

    code = "DOCUMENT_UNREADABLE"


class FingerprintMismatchError(ExtractorError):
    """El layout del documento no coincide con el fingerprint del perfil."""

    code = "FINGERPRINT_MISMATCH"


class DocumentTooLargeError(ExtractorError):
    """El documento supera los límites de tamaño o páginas."""

    code = "DOCUMENT_TOO_LARGE"


class UnsupportedContentTypeError(ExtractorError):
    """El content_type no está soportado."""

    code = "UNSUPPORTED_CONTENT_TYPE"


class Sha256MismatchError(ExtractorError):
    """El hash del documento no coincide con el declarado."""

    code = "SHA256_MISMATCH"


class NoRowsFoundError(ExtractorError):
    """El documento se leyó pero el perfil no produjo ninguna fila."""

    code = "NO_ROWS_FOUND"


class SourceFetchFailedError(ExtractorError):
    """Falló la descarga del documento desde la URL firmada."""

    code = "SOURCE_FETCH_FAILED"


class ExtractionTimeoutError(ExtractorError):
    """La extracción superó el timeout configurado."""

    code = "EXTRACTION_TIMEOUT"


class ConcurrencyLimitError(ExtractorError):
    """La instancia ya tiene MAX_CONCURRENCY extracciones en curso."""

    code = "CONCURRENCY_LIMIT"


class InvalidRequestError(ExtractorError):
    """La petición HTTP es inválida (campos faltantes o excluyentes)."""

    code = "INVALID_REQUEST"
