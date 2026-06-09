from fastapi.testclient import TestClient

from app.main import app
from app.services.discogs_service import DiscogsClientError


def test_discogs_service_dependency_reuses_search_cache() -> None:
    from app.api.routes.releases import get_discogs_service

    get_discogs_service.cache_clear()

    try:
        assert get_discogs_service() is get_discogs_service()
    finally:
        get_discogs_service.cache_clear()


def test_search_releases_endpoint_returns_discogs_results(
    build_stub_discogs_search_service,
    override_discogs_service,
) -> None:
    service = build_stub_discogs_search_service()
    override_discogs_service(service)

    with TestClient(app) as client:
        response = client.get(
            "/api/v1/releases/search",
            params={"artist": "Boards of Canada", "title": "Music", "catalog": "WARPLP55", "limit": 10, "offset": 0},
        )

    assert response.status_code == 200
    assert response.json() == {
        "results": [
            {
                "discogs_release_id": 555123,
                "artist": "Boards of Canada",
                "title": "Music Has The Right To Children",
                "year": 1998,
                "label": "Warp Records",
                "catalog_number": "WARPLP55",
                "thumbnail_url": "https://img.discogs.com/thumb.jpg",
                "format": "Vinyl, LP",
            }
        ],
        "limit": 10,
        "offset": 0,
    }
    assert service.calls == [
        {
            "artist": "Boards of Canada",
            "title": "Music",
            "catalog_number": "WARPLP55",
            "barcode": None,
            "year": None,
            "query": None,
            "limit": 10,
            "offset": 0,
        }
    ]


def test_search_releases_endpoint_requires_search_field(
    build_stub_discogs_search_service,
    override_discogs_service,
) -> None:
    service = build_stub_discogs_search_service()
    override_discogs_service(service)

    with TestClient(app) as client:
        response = client.get("/api/v1/releases/search")

    assert response.status_code == 422
    assert response.json() == {"detail": "At least one search field is required."}
    assert service.calls == []


def test_search_releases_endpoint_returns_empty_results(
    build_stub_discogs_search_service,
    override_discogs_service,
) -> None:
    service = build_stub_discogs_search_service()
    service.payload = {"results": []}
    override_discogs_service(service)

    with TestClient(app) as client:
        response = client.get("/api/v1/releases/search", params={"query": "unknown"})

    assert response.status_code == 200
    assert response.json() == {"results": [], "limit": 10, "offset": 0}


def test_search_releases_endpoint_trims_discogs_artist_number_suffix(
    build_stub_discogs_search_service,
    override_discogs_service,
) -> None:
    service = build_stub_discogs_search_service()
    service.payload["results"][0]["title"] = "Karma (54), Mutt (2) - The Warning"
    override_discogs_service(service)

    with TestClient(app) as client:
        response = client.get("/api/v1/releases/search", params={"query": "karma warning"})

    assert response.status_code == 200
    assert response.json()["results"][0]["artist"] == "Karma, Mutt"
    assert response.json()["results"][0]["title"] == "The Warning"


def test_search_releases_endpoint_maps_discogs_errors(
    build_stub_discogs_search_service,
    override_discogs_service,
) -> None:
    service = build_stub_discogs_search_service()
    service.error = DiscogsClientError("Discogs API error (503): unavailable")
    override_discogs_service(service)

    with TestClient(app) as client:
        response = client.get("/api/v1/releases/search", params={"query": "boards"})

    assert response.status_code == 502
    assert response.json() == {"detail": "Discogs API error (503): unavailable"}


def test_import_release_endpoint_returns_created_release_id(
    build_stub_release_import_service,
    override_release_import_service,
) -> None:
    service = build_stub_release_import_service()
    override_release_import_service(service)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/releases/import",
            json={"discogs_release_id": 555123},
        )

    assert response.status_code == 201
    assert response.json() == {
        "release_id": "release-123",
        "discogs_release_id": 555123,
        "status": "created",
    }
    assert service.import_calls == [(555123, False)]


def test_import_release_endpoint_returns_404_for_missing_discogs_release(
    build_stub_release_import_service,
    override_release_import_service,
) -> None:
    service = build_stub_release_import_service()
    service.import_error = DiscogsClientError("Discogs API error (404): release not found")
    override_release_import_service(service)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/releases/import",
            json={"discogs_release_id": 999999},
        )

    assert response.status_code == 404
    assert response.json() == {"detail": "Discogs API error (404): release not found"}


def test_import_release_endpoint_sanitizes_request_validation_errors(
    build_stub_release_import_service,
    override_release_import_service,
) -> None:
    service = build_stub_release_import_service()
    override_release_import_service(service)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/releases/import",
            json={"discogs_release_id": "not-an-integer"},
        )

    assert response.status_code == 422
    assert response.json() == {
        "error": {
            "code": "invalid_request",
            "message": "Input should be a valid integer, unable to parse string as an integer",
        }
    }


def test_get_release_endpoint_returns_local_release_metadata(
    build_stub_release_import_service,
    override_release_import_service,
) -> None:
    service = build_stub_release_import_service()
    override_release_import_service(service)

    with TestClient(app) as client:
        response = client.get("/api/v1/releases/release-123")

    assert response.status_code == 200
    assert response.json() == {
        "id": "release-123",
        "discogs_release_id": 555123,
        "artist": "Boards of Canada",
        "title": "Music Has The Right To Children",
        "year": 1998,
        "format": None,
        "label": "Warp Records",
        "catalog_number": "WARPLP55",
        "barcode": "5021603065515",
        "genres": ["Electronic"],
        "styles": ["IDM"],
        "thumbnail_url": None,
        "cover_image_url": "https://img.discogs.com/cover.jpg",
        "in_collection": False,
        "collection_added_at": None,
        "collection_removed_at": None,
        "last_discogs_sync_at": None,
        "discogs_instance_id": None,
        "has_full_discogs_info": True,
        "available_sides": ["A", "AA"],
        "available_side_options": [
            {"value": "A", "label": "Side A", "side": "A", "disc_number": None},
            {"value": "AA", "label": "Side AA", "side": "AA", "disc_number": None},
        ],
        "tracklist": [
            {"position": "A1", "title": "Wildlife Analysis", "duration": "1:17"},
            {"position": "A2", "title": "An Eagle In Your Mind", "duration": None},
        ],
        "discogs_artists": [
            {"name": "Boards of Canada", "discogs_artist_id": 194},
        ],
        "created_at": "2026-04-19T00:00:00Z",
        "updated_at": "2026-04-19T00:00:00Z",
    }
    assert service.lookup_calls == ["release-123"]


def test_refresh_release_endpoint_fetches_full_release(
    build_stub_release_import_service,
    override_release_import_service,
) -> None:
    service = build_stub_release_import_service()
    override_release_import_service(service)

    with TestClient(app) as client:
        response = client.post("/api/v1/releases/release-123/refresh")

    assert response.status_code == 200
    assert response.json()["has_full_discogs_info"] is True
    assert service.refresh_calls == ["release-123"]
    assert service.import_calls == [(555123, True)]


def test_refresh_release_endpoint_returns_404_when_release_missing(
    build_stub_release_import_service,
    override_release_import_service,
) -> None:
    service = build_stub_release_import_service()
    override_release_import_service(service)

    with TestClient(app) as client:
        response = client.post("/api/v1/releases/missing-release/refresh")

    assert response.status_code == 404
    assert response.json() == {"detail": "Release 'missing-release' was not found."}


def test_get_release_endpoint_returns_404_when_release_missing(
    build_stub_release_import_service,
    override_release_import_service,
) -> None:
    service = build_stub_release_import_service()
    override_release_import_service(service)

    with TestClient(app) as client:
        response = client.get("/api/v1/releases/missing-release")

    assert response.status_code == 404
    assert response.json() == {"detail": "Release 'missing-release' was not found."}
