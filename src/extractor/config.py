"""Application settings. Único punto que lee variables de entorno."""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated, Literal

from pydantic import BeforeValidator, Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


def _parse_hosts(value: object) -> list[str]:
    if isinstance(value, list):
        hosts = [str(item).strip() for item in value if str(item).strip()]
    elif isinstance(value, str):
        hosts = [part.strip() for part in value.split(",") if part.strip()]
    else:
        msg = "FETCH_ALLOWED_HOSTS must be a comma-separated string or a list"
        raise TypeError(msg)
    if not hosts:
        msg = "FETCH_ALLOWED_HOSTS must contain at least one host"
        raise ValueError(msg)
    return hosts


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    extractor_shared_secret: str = Field(min_length=32)
    log_level: str = "INFO"
    environment: Literal["development", "staging", "production"] = "production"

    max_request_bytes: int = 52_428_800
    max_document_bytes: int = 52_428_800
    max_pages: int = 200
    max_concurrency: int = 4
    extraction_timeout_seconds: int = 120
    fetch_timeout_seconds: int = 30
    fetch_allowed_hosts: Annotated[list[str], NoDecode, BeforeValidator(_parse_hosts)]

    ocr_enabled: bool = False
    ocr_density_threshold: float = 5.0
    ocr_min_confidence: int = 70
    tesseract_cmd: str = "tesseract"

    uvicorn_workers: int = 2

    @field_validator("log_level")
    @classmethod
    def _upper_log_level(cls, value: str) -> str:
        return value.upper()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings singleton."""
    return Settings()


def clear_settings_cache() -> None:
    """Drop the cached settings (for tests)."""
    get_settings.cache_clear()
