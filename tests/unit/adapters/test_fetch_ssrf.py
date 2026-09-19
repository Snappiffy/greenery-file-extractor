"""Tests SSRF del HttpFetcher (cinco mitigaciones)."""

from __future__ import annotations

from unittest.mock import patch

import httpx
import pytest

from extractor.adapters.fetch.http_fetcher import HttpFetcher
from extractor.domain.errors import DocumentTooLargeError, SourceFetchFailedError


def _fetcher(**kwargs: object) -> HttpFetcher:
    defaults: dict[str, object] = {
        "allowed_hosts": ["cdn.example.com"],
        "timeout_seconds": 5.0,
        "max_bytes": 100,
    }
    defaults.update(kwargs)
    return HttpFetcher(**defaults)  # type: ignore[arg-type]


def test_ssrf_rejects_non_https() -> None:
    with pytest.raises(SourceFetchFailedError) as exc:
        _fetcher().fetch("http://cdn.example.com/file.pdf")
    assert exc.value.detail["reason"] == "scheme"


def test_ssrf_rejects_host_not_in_allowlist() -> None:
    with pytest.raises(SourceFetchFailedError) as exc:
        _fetcher().fetch("https://evil.example.com/file.pdf")
    assert exc.value.detail["reason"] == "host_not_allowed"


def test_ssrf_rejects_private_ip_after_dns() -> None:
    with patch("extractor.adapters.fetch.http_fetcher.socket.getaddrinfo") as gai:
        gai.return_value = [(0, 0, 0, "", ("169.254.169.254", 443))]
        with pytest.raises(SourceFetchFailedError) as exc:
            _fetcher().fetch("https://cdn.example.com/file.pdf")
    assert exc.value.detail["reason"] == "private_ip"


def test_ssrf_does_not_follow_redirects() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(302, headers={"Location": "https://cdn.example.com/x"})
    )
    client = httpx.Client(transport=transport, follow_redirects=False)
    with patch("extractor.adapters.fetch.http_fetcher.socket.getaddrinfo") as gai:
        gai.return_value = [(0, 0, 0, "", ("1.2.3.4", 443))]
        fetcher = _fetcher(client=client)
        with pytest.raises(SourceFetchFailedError) as exc:
            fetcher.fetch("https://cdn.example.com/file.pdf")
    assert exc.value.detail["reason"] == "redirect"
    client.close()


def test_ssrf_cuts_stream_over_max_bytes() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"x" * 200)

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport, follow_redirects=False)
    with patch("extractor.adapters.fetch.http_fetcher.socket.getaddrinfo") as gai:
        gai.return_value = [(0, 0, 0, "", ("1.2.3.4", 443))]
        fetcher = _fetcher(client=client, max_bytes=50)
        with pytest.raises(DocumentTooLargeError):
            fetcher.fetch("https://cdn.example.com/file.pdf")
    client.close()
