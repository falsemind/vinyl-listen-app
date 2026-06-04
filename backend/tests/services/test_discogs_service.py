from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlparse

from app.models.discogs_release_cache import DiscogsReleaseCache
from app.services.discogs_service import DiscogsClient, DiscogsRateLimiter, DiscogsResponse, DiscogsService


def test_search_by_barcode_uses_discogs_search_endpoint(
    recording_transport_factory,
    build_discogs_client,
    in_memory_discogs_repository_factory,
) -> None:
    transport = recording_transport_factory(payload={"results": [{"id": 12345}]})
    service = DiscogsService(client=build_discogs_client(transport), repository=in_memory_discogs_repository_factory())

    payload = service.search_by_barcode("0123456789012", limit=5, offset=5)

    assert payload == {"results": [{"id": 12345}]}
    assert len(transport.calls) == 1
    request = transport.calls[0]
    parsed_url = urlparse(request["url"])
    query = parse_qs(parsed_url.query)

    assert parsed_url.path == "/database/search"
    assert query["barcode"] == ["0123456789012"]
    assert query["type"] == ["release"]
    assert query["per_page"] == ["5"]
    assert query["page"] == ["2"]
    assert request["headers"]["Authorization"] == "Discogs token=secret-token"


def test_search_releases_maps_catalog_artist_and_title_params(
    recording_transport_factory,
    build_discogs_client,
    in_memory_discogs_repository_factory,
) -> None:
    transport = recording_transport_factory()
    service = DiscogsService(client=build_discogs_client(transport), repository=in_memory_discogs_repository_factory())

    service.search_releases(artist="Air", title="Moon Safari", catalog_number="7243 8 44978 1 8")

    request = transport.calls[0]
    query = parse_qs(urlparse(request["url"]).query)

    assert query["artist"] == ["Air"]
    assert query["release_title"] == ["Moon Safari"]
    assert query["catno"] == ["7243 8 44978 1 8"]
    assert "barcode" not in query


def test_fetch_collection_releases_fetches_all_folder_pages(
    queue_transport_factory,
    build_discogs_client,
    in_memory_discogs_repository_factory,
) -> None:
    transport = queue_transport_factory(
        [
            {
                "pagination": {"page": 1, "pages": 2, "per_page": 50, "items": 2},
                "releases": [{"id": 101}],
            },
            {
                "pagination": {"page": 2, "pages": 2, "per_page": 50, "items": 2},
                "releases": [{"id": 202}],
            },
        ]
    )
    service = DiscogsService(client=build_discogs_client(transport), repository=in_memory_discogs_repository_factory())

    releases = service.fetch_collection_releases(username="alex", per_page=50)

    assert releases == [{"id": 101}, {"id": 202}]
    assert len(transport.calls) == 2
    first_url = urlparse(transport.calls[0]["url"])
    second_url = urlparse(transport.calls[1]["url"])
    first_query = parse_qs(first_url.query)
    second_query = parse_qs(second_url.query)
    assert first_url.path == "/users/alex/collection/folders/0/releases"
    assert first_query["page"] == ["1"]
    assert first_query["per_page"] == ["50"]
    assert first_query["sort"] == ["added"]
    assert first_query["sort_order"] == ["desc"]
    assert second_query["page"] == ["2"]


def test_search_releases_caches_identical_queries(
    recording_transport_factory,
    build_discogs_client,
    in_memory_discogs_repository_factory,
) -> None:
    transport = recording_transport_factory(payload={"results": [{"id": 999}]})
    service = DiscogsService(client=build_discogs_client(transport), repository=in_memory_discogs_repository_factory())

    first_payload = service.search_releases(artist="Air", title="Moon Safari", limit=10, offset=0)
    second_payload = service.search_releases(artist="Air", title="Moon Safari", limit=10, offset=0)

    assert first_payload == {"results": [{"id": 999}]}
    assert second_payload == {"results": [{"id": 999}]}
    assert len(transport.calls) == 1


def test_search_releases_supports_non_aligned_offset(
    queue_transport_factory,
    build_discogs_client,
    in_memory_discogs_repository_factory,
) -> None:
    transport = queue_transport_factory(
        payloads=[
            {"results": [{"id": 13}, {"id": 14}, {"id": 15}]},
            {"results": [{"id": 16}, {"id": 17}, {"id": 18}]},
        ]
    )
    service = DiscogsService(client=build_discogs_client(transport), repository=in_memory_discogs_repository_factory())

    payload = service.search_releases(barcode="abc123", limit=3, offset=4)

    assert payload["results"] == [{"id": 14}, {"id": 15}, {"id": 16}]
    assert len(transport.calls) == 2

    first_query = parse_qs(urlparse(transport.calls[0]["url"]).query)
    second_query = parse_qs(urlparse(transport.calls[1]["url"]).query)

    assert first_query["per_page"] == ["3"]
    assert first_query["page"] == ["2"]
    assert second_query["per_page"] == ["3"]
    assert second_query["page"] == ["3"]


def test_fetch_release_returns_fresh_cached_payload_without_api_call(
    recording_transport_factory,
    build_discogs_client,
    in_memory_discogs_repository_factory,
) -> None:
    cached_payload = {"id": 67890, "title": "Cached Release"}
    repository = in_memory_discogs_repository_factory(
        cache_entry=DiscogsReleaseCache(
            discogs_release_id=67890,
            raw_discogs_json=cached_payload,
            cached_at=datetime.now(UTC) - timedelta(minutes=5),
            last_accessed_at=None,
        )
    )
    transport = recording_transport_factory(payload={"id": 67890, "title": "Remote Release"})
    service = DiscogsService(
        client=build_discogs_client(transport),
        repository=repository,
        cache_ttl=timedelta(hours=1),
    )

    payload = service.fetch_release(db=object(), discogs_release_id=67890)

    assert payload == cached_payload
    assert transport.calls == []
    assert repository.touch_count == 1


def test_fetch_release_fetches_and_caches_on_cache_miss(
    recording_transport_factory,
    build_discogs_client,
    in_memory_discogs_repository_factory,
) -> None:
    repository = in_memory_discogs_repository_factory()
    transport = recording_transport_factory(payload={"id": 555123, "title": "Fresh Remote Release"})
    service = DiscogsService(
        client=build_discogs_client(transport),
        repository=repository,
        cache_ttl=timedelta(hours=1),
    )

    payload = service.fetch_release(db=object(), discogs_release_id=555123)

    assert payload == {"id": 555123, "title": "Fresh Remote Release"}
    assert len(transport.calls) == 1
    assert repository.upserts == [(555123, {"id": 555123, "title": "Fresh Remote Release"})]


def test_fetch_release_refreshes_stale_cache(
    recording_transport_factory,
    build_discogs_client,
    in_memory_discogs_repository_factory,
) -> None:
    repository = in_memory_discogs_repository_factory(
        cache_entry=DiscogsReleaseCache(
            discogs_release_id=2468,
            raw_discogs_json={"id": 2468, "title": "Stale"},
            cached_at=datetime.now(UTC) - timedelta(days=2),
            last_accessed_at=None,
        )
    )
    transport = recording_transport_factory(payload={"id": 2468, "title": "Refreshed"})
    service = DiscogsService(
        client=build_discogs_client(transport),
        repository=repository,
        cache_ttl=timedelta(hours=12),
    )

    payload = service.fetch_release(db=object(), discogs_release_id=2468)

    assert payload == {"id": 2468, "title": "Refreshed"}
    assert len(transport.calls) == 1
    assert repository.upserts == [(2468, {"id": 2468, "title": "Refreshed"})]


def test_rate_limiter_waits_between_close_requests() -> None:
    sleep_calls: list[float] = []
    clock_values = iter([0.0, 0.25, 1.0])

    limiter = DiscogsRateLimiter(
        requests_per_minute=60,
        sleep_func=lambda seconds: sleep_calls.append(seconds),
        clock=lambda: next(clock_values),
    )

    limiter.wait()
    limiter.wait()

    assert sleep_calls == [0.75]


def test_rate_limiter_tracks_discogs_response_headers() -> None:
    limiter = DiscogsRateLimiter(
        requests_per_minute=60,
        sleep_func=lambda _seconds: None,
        clock=lambda: 42.0,
    )

    limiter.observe_response_headers(
        {
            "X-Discogs-Ratelimit": "60",
            "X-Discogs-Ratelimit-Used": "58",
            "X-Discogs-Ratelimit-Remaining": "2",
        }
    )

    state = limiter.rate_limit_state
    assert state is not None
    assert state.limit == 60
    assert state.used == 58
    assert state.remaining == 2
    assert state.observed_at == 42.0


def test_rate_limiter_waits_when_observed_discogs_quota_is_exhausted() -> None:
    sleep_calls: list[float] = []
    current_time = 10.0

    limiter = DiscogsRateLimiter(
        requests_per_minute=60,
        sleep_func=lambda seconds: sleep_calls.append(seconds),
        clock=lambda: current_time,
    )
    limiter.observe_response_headers(
        {
            "X-Discogs-Ratelimit": "60",
            "X-Discogs-Ratelimit-Used": "60",
            "X-Discogs-Ratelimit-Remaining": "0",
        }
    )

    current_time = 25.0
    limiter.wait()

    assert sleep_calls == [45.0]


def test_rate_limiter_ignores_malformed_discogs_headers() -> None:
    limiter = DiscogsRateLimiter(
        requests_per_minute=60,
        sleep_func=lambda _seconds: None,
        clock=lambda: 42.0,
    )

    limiter.observe_response_headers(
        {
            "X-Discogs-Ratelimit": "many",
            "X-Discogs-Ratelimit-Used": "nope",
            "X-Discogs-Ratelimit-Remaining": "",
        }
    )

    assert limiter.rate_limit_state is None


def test_discogs_client_observes_rate_limit_headers(discogs_api_config) -> None:
    limiter = DiscogsRateLimiter(
        requests_per_minute=60,
        sleep_func=lambda _seconds: None,
        clock=lambda: 42.0,
    )

    def transport(url: str, headers: dict[str, str], timeout: float) -> DiscogsResponse:
        _ = (url, headers, timeout)
        return DiscogsResponse(
            payload={"results": []},
            headers={
                "X-Discogs-Ratelimit": "60",
                "X-Discogs-Ratelimit-Used": "12",
                "X-Discogs-Ratelimit-Remaining": "48",
            },
        )

    client = DiscogsClient(config=discogs_api_config, rate_limiter=limiter, transport=transport)

    assert client.get("/database/search") == {"results": []}
    state = limiter.rate_limit_state
    assert state is not None
    assert state.limit == 60
    assert state.used == 12
    assert state.remaining == 48
