"""Bearer authentication against the shared secret."""

from __future__ import annotations

import secrets

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from extractor.config import Settings, get_settings

_bearer_scheme = HTTPBearer(auto_error=False)


def require_bearer(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    settings: Settings = Depends(get_settings),
) -> None:
    """Reject the request unless the bearer token matches the shared secret."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "UNAUTHORIZED",
                    "message": "Missing or invalid Authorization header.",
                    "detail": {},
                }
            },
            headers={"WWW-Authenticate": "Bearer"},
        )

    expected = settings.extractor_shared_secret.encode("utf-8")
    provided = credentials.credentials.encode("utf-8")
    if len(expected) != len(provided) or not secrets.compare_digest(expected, provided):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "UNAUTHORIZED",
                    "message": "Invalid shared secret.",
                    "detail": {},
                }
            },
            headers={"WWW-Authenticate": "Bearer"},
        )
