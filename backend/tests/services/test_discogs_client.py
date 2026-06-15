from datetime import UTC, datetime, timedelta
from io import BytesIO
from unittest.mock import sentinel
from urllib.error import HTTPError, URLError

import pytest

from app.services.discogs_service import (
    DiscogsClientError,
    DiscogsService,
)


def test_discogs_client_parses_http_error_message(build_discogs_client) -> None:
    def transport(url: str, headers: dict[str, str], timeout: float) -> dict:
        del headers, timeout
        raise HTTPError(
            url=url,
            code=401,
            msg="Unauthorized",
            hdrs=None,
            fp=BytesIO(b'{"message": "invalid token"}'),
        )

    client = build_discogs_client(transport)

    with pytest.raises(DiscogsClientError, match=r"Discogs API error \(401\): invalid token"):
        client.get("/database/search", params={"barcode": "123"})


def test_discogs_client_wraps_network_errors(build_discogs_client) -> None:
    def transport(url: str, headers: dict[str, str], timeout: float) -> dict:
        del url, headers, timeout
        raise URLError("network down")

    client = build_discogs_client(transport)

    with pytest.raises(DiscogsClientError, match="Unable to reach Discogs API: network down"):
        client.get("/database/search", params={"barcode": "123"})


def test_search_cache_expires_after_ttl(build_discogs_client) -> None:
    current_time = datetime(2026, 4, 18, 12, 0, tzinfo=UTC)
    payloads = iter(
        [
            {"results": [{"id": 1}]},
            {"results": [{"id": 2}]},
        ]
    )
    calls: list[str] = []

    def transport(url: str, headers: dict[str, str], timeout: float) -> dict:
        del headers, timeout
        calls.append(url)
        return next(payloads)

    client = build_discogs_client(transport)
    service = DiscogsService(
        client=client,
        cache_ttl=timedelta(seconds=30),
        now_provider=lambda: current_time,
    )

    first_payload = service.search_releases(artist="Air", limit=10, offset=0)
    second_payload = service.search_releases(artist="Air", limit=10, offset=0)
    current_time = current_time.replace(minute=current_time.minute + 1)
    third_payload = service.search_releases(artist="Air", limit=10, offset=0)

    assert first_payload == {"results": [{"id": 1}]}
    assert second_payload == {"results": [{"id": 1}]}
    assert third_payload == {"results": [{"id": 2}]}
    assert len(calls) == 2


def test_discogs_client_builds_ssl_context_from_certifi_bundle(
    build_discogs_client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = build_discogs_client(lambda _url, _headers, _timeout: {})
    create_default_context_calls: list[str] = []

    def fake_where() -> str:
        return "/tmp/discogs-certifi.pem"

    def fake_create_default_context(*, cafile: str):
        create_default_context_calls.append(cafile)
        return sentinel.ssl_context

    monkeypatch.setattr("app.services.discogs_service.certifi.where", fake_where)
    monkeypatch.setattr("app.services.discogs_service.ssl.create_default_context", fake_create_default_context)

    context = client._build_ssl_context()

    assert context is sentinel.ssl_context
    assert create_default_context_calls == ["/tmp/discogs-certifi.pem"]
