"""Descarga de documentos con mitigaciones SSRF."""

from __future__ import annotations

import ipaddress
import socket
from typing import Protocol
from urllib.parse import urlparse

import httpx

from extractor.domain.errors import DocumentTooLargeError, SourceFetchFailedError


class Fetcher(Protocol):
    def fetch(self, url: str) -> bytes: ...


class HttpFetcher:
    """Fetcher HTTPS con allowlist, sin redirects, y corte por tamaño."""

    def __init__(
        self,
        *,
        allowed_hosts: list[str],
        timeout_seconds: float,
        max_bytes: int,
        client: httpx.Client | None = None,
    ) -> None:
        self._allowed_hosts = {host.lower() for host in allowed_hosts}
        self._timeout = timeout_seconds
        self._max_bytes = max_bytes
        self._client = client

    def fetch(self, url: str) -> bytes:
        parsed = urlparse(url)
        if parsed.scheme.lower() != "https":
            raise SourceFetchFailedError(
                "Only https URLs are allowed.",
                detail={"reason": "scheme", "scheme": parsed.scheme},
            )
        host = (parsed.hostname or "").lower()
        if not host:
            raise SourceFetchFailedError(
                "URL host is missing.",
                detail={"reason": "missing_host"},
            )
        if host not in self._allowed_hosts:
            raise SourceFetchFailedError(
                "Host is not in FETCH_ALLOWED_HOSTS.",
                detail={"reason": "host_not_allowed", "host": host},
            )

        self._assert_public_ip(host)

        owns_client = self._client is None
        client = self._client or httpx.Client(
            timeout=self._timeout,
            follow_redirects=False,
        )
        try:
            with client.stream("GET", url) as response:
                if response.is_redirect:
                    raise SourceFetchFailedError(
                        "Redirects are not followed.",
                        detail={"reason": "redirect", "status": response.status_code},
                    )
                if response.status_code < 200 or response.status_code >= 300:
                    raise SourceFetchFailedError(
                        f"Source returned HTTP {response.status_code}.",
                        detail={"reason": "http_status", "status": response.status_code},
                    )
                chunks: list[bytes] = []
                total = 0
                for chunk in response.iter_bytes():
                    total += len(chunk)
                    if total > self._max_bytes:
                        raise DocumentTooLargeError(
                            "Document exceeds MAX_DOCUMENT_BYTES during download.",
                            detail={
                                "reason": "max_document_bytes",
                                "max_bytes": self._max_bytes,
                            },
                        )
                    chunks.append(chunk)
                return b"".join(chunks)
        except (DocumentTooLargeError, SourceFetchFailedError):
            raise
        except httpx.HTTPError as exc:
            raise SourceFetchFailedError(
                "Failed to fetch document.",
                detail={"reason": "http_error", "error": str(exc)},
            ) from exc
        finally:
            if owns_client:
                client.close()

    def _assert_public_ip(self, host: str) -> None:
        try:
            infos = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        except socket.gaierror as exc:
            raise SourceFetchFailedError(
                "DNS resolution failed.",
                detail={"reason": "dns", "host": host, "error": str(exc)},
            ) from exc

        for info in infos:
            ip_str = info[4][0]
            ip = ipaddress.ip_address(ip_str)
            if (
                ip.is_private
                or ip.is_loopback
                or ip.is_link_local
                or ip.is_reserved
                or ip.is_multicast
            ):
                raise SourceFetchFailedError(
                    "Resolved IP is not publicly routable.",
                    detail={"reason": "private_ip", "host": host, "ip": ip_str},
                )
