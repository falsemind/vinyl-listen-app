from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, status
from fastapi.testclient import TestClient

from app.api.routes.releases import get_manual_release_repository, get_releases_repository
from app.main import app
from app.services.discogs_service import DiscogsClientError, DiscogsConfigurationError
from app.services.release_import_service import ReleaseImportResult
from tests.fixtures.api_stubs import SessionStub


def _manual_release_stub() -> SimpleNamespace:
    return SimpleNamespace(
        id="manual-release-1",
        artist="KarmaTest",
        title="KarmaTestTitle",
        year=1998,
        label="KarmaTestLabel",
        catalog_number="KarmaTest01",
        barcode=None,
        format="Vinyl",
        genres=["Electronic"],
        styles=["Techno"],
        cover_thumbnail_url=None,
        cover_image_url=None,
        in_collection=True,
        collection_added_at=datetime(2026, 6, 21, tzinfo=UTC),
        collection_removed_at=None,
        is_favorite=False,
        tracklist=[
            {
                "position": "1",
                "title": "KarmaTestTrack",
                "duration": "5:00",
                "credits": [{"role": "Remix", "name": "DJ Madd"}],
            }
        ],
        created_at=datetime(2026, 6, 21, tzinfo=UTC),
        updated_at=datetime(2026, 6, 21, tzinfo=UTC),
    )


class ManualReleaseRepositoryStub:
    def __init__(self, release: SimpleNamespace | None = None) -> None:
        self.release = release or _manual_release_stub()
        self.lookup_calls: list[tuple[str, str]] = []
        self.favorite_calls: list[tuple[str, bool]] = []
        self.deactivate_calls: list[str] = []
        self.reactivate_calls: list[str] = []

    def get_release(self, _db, release_id: str, *, user_id: str):
        self.lookup_calls.append((release_id, user_id))
        if release_id != self.release.id or user_id != "test-user":
            return None
        return self.release

    def set_favorite(self, _db, release, *, is_favorite: bool):
        self.favorite_calls.append((release.id, is_favorite))
        release.is_favorite = is_favorite
        return release

    def deactivate_collection_membership(self, _db, release, *, removed_at: datetime):
        self.deactivate_calls.append(release.id)
        release.in_collection = False
        release.collection_removed_at = removed_at
        return release

    def reactivate_collection_membership(self, _db, release, *, added_at: datetime):
        self.reactivate_calls.append(release.id)
        release.in_collection = True
        release.collection_added_at = added_at
        release.collection_removed_at = None
        return release


def test_discogs_service_dependency_requires_saved_token() -> None:
    from app.api.routes.releases import get_discogs_service

    class MissingIntegrationService:
        def build_discogs_service(self, _db: object, *, user_id: str | None = None) -> object:
            _ = user_id
            raise DiscogsConfigurationError("Discogs token is not configured.")

    with pytest.raises(HTTPException) as error:
        get_discogs_service(
            db=object(),
            current_user=SimpleNamespace(account=SimpleNamespace(id="test-user")),
            integration_service=MissingIntegrationService(),
        )

    assert error.value.status_code == status.HTTP_400_BAD_REQUEST
    assert error.value.detail == "Discogs access token is required."


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


def test_import_release_endpoint_maps_discogs_configuration_errors(
    build_stub_release_import_service,
    override_release_import_service,
) -> None:
    service = build_stub_release_import_service()
    service.import_error = DiscogsConfigurationError("Discogs token is not configured.")
    override_release_import_service(service)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/releases/import",
            json={"discogs_release_id": 555123},
        )

    assert response.status_code == 400
    assert response.json() == {"detail": "Discogs access token is required."}


def test_import_release_to_collection_endpoint_returns_created_release_id(
    build_stub_release_import_service,
    override_release_import_service,
) -> None:
    service = build_stub_release_import_service()
    override_release_import_service(service)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/releases/import-to-collection",
            json={"discogs_release_id": 555123},
        )

    assert response.status_code == 201
    assert response.json() == {
        "release_id": "release-123",
        "discogs_release_id": 555123,
        "status": "created",
    }
    assert service.collection_import_calls == [(555123, False)]
    assert service.release.in_collection is True


def test_import_release_to_collection_endpoint_returns_200_for_existing_release(
    build_stub_release_import_service,
    override_release_import_service,
) -> None:
    service = build_stub_release_import_service()
    service.import_result = ReleaseImportResult(release=service.release, created=False)
    override_release_import_service(service)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/releases/import-to-collection",
            json={"discogs_release_id": 555123, "force_refresh": True},
        )

    assert response.status_code == 200
    assert response.json()["status"] == "updated"
    assert service.collection_import_calls == [(555123, True)]


def test_import_release_to_collection_endpoint_maps_discogs_errors(
    build_stub_release_import_service,
    override_release_import_service,
) -> None:
    service = build_stub_release_import_service()
    service.collection_import_error = DiscogsClientError("Discogs API error (404): release not found")
    override_release_import_service(service)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/releases/import-to-collection",
            json={"discogs_release_id": 999999},
        )

    assert response.status_code == 404
    assert response.json() == {"detail": "Discogs API error (404): release not found"}


def test_import_release_to_collection_endpoint_maps_discogs_configuration_errors(
    build_stub_release_import_service,
    override_release_import_service,
) -> None:
    service = build_stub_release_import_service()
    service.collection_import_error = DiscogsConfigurationError("Discogs token is not configured.")
    override_release_import_service(service)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/releases/import-to-collection",
            json={"discogs_release_id": 555123},
        )

    assert response.status_code == 400
    assert response.json() == {"detail": "Discogs access token is required."}


def test_import_client_discogs_release_endpoint_returns_created_release_id(
    build_stub_release_import_service,
    override_release_import_service,
) -> None:
    service = build_stub_release_import_service()
    override_release_import_service(service)
    payload = {
        "id": 555123,
        "title": "Music Has The Right To Children",
        "artists_sort": "Boards of Canada",
    }

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/releases/import/client-discogs",
            json={"discogs_release": payload},
        )

    assert response.status_code == 201
    assert response.json() == {
        "release_id": "release-123",
        "discogs_release_id": 555123,
        "status": "created",
    }
    assert service.client_import_calls == [payload]
    assert service.import_calls == []


def test_import_client_discogs_release_endpoint_maps_validation_errors(
    build_stub_release_import_service,
    override_release_import_service,
) -> None:
    service = build_stub_release_import_service()
    service.client_import_error = ValueError("Discogs payload is missing a release title.")
    override_release_import_service(service)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/releases/import/client-discogs",
            json={"discogs_release": {"id": 555123}},
        )

    assert response.status_code == 422
    assert response.json() == {"detail": "Discogs payload is missing a release title."}


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
        "is_favorite": False,
        "has_full_discogs_info": True,
        "available_sides": ["A", "AA"],
        "available_side_options": [
            {"value": "A", "label": "Side A", "side": "A", "disc_number": None},
            {"value": "AA", "label": "Side AA", "side": "AA", "disc_number": None},
        ],
        "tracklist": [
            {"position": "A1", "title": "Wildlife Analysis", "duration": "1:17", "artists": [], "extra_artists": []},
            {
                "position": "A2",
                "title": "An Eagle In Your Mind",
                "duration": None,
                "artists": [
                    {"name": "Boards of Canada", "join": "&", "discogs_artist_id": 194},
                    {"name": "Plaid", "join": None, "discogs_artist_id": 2470},
                ],
                "extra_artists": [{"name": "Plaid", "role": "Remix"}],
            },
        ],
        "discogs_artists": [
            {"name": "Boards of Canada", "discogs_artist_id": 194},
        ],
        "created_at": "2026-04-19T00:00:00Z",
        "updated_at": "2026-04-19T00:00:00Z",
    }
    assert service.lookup_calls == ["release-123"]


def test_get_release_endpoint_returns_manual_release_metadata(
    build_stub_release_import_service,
    override_release_import_service,
) -> None:
    service = build_stub_release_import_service()
    override_release_import_service(service)

    class ManualReleaseRepositoryStub:
        def __init__(self) -> None:
            self.lookup_calls: list[tuple[str, str]] = []

        def get_release(self, _db, release_id: str, *, user_id: str):
            self.lookup_calls.append((release_id, user_id))
            if release_id != "manual-release-1":
                return None
            return SimpleNamespace(
                id="manual-release-1",
                artist="KarmaTest",
                title="KarmaTestTitle",
                year=1998,
                label="KarmaTestLabel",
                catalog_number="KarmaTest01",
                barcode=None,
                format="Vinyl",
                genres=["Electronic"],
                styles=["Techno"],
                cover_thumbnail_url=None,
                cover_image_url=None,
                in_collection=True,
                collection_added_at=datetime(2026, 6, 21, tzinfo=UTC),
                collection_removed_at=None,
                is_favorite=False,
                tracklist=[
                    {
                        "position": "1",
                        "title": "KarmaTestTrack",
                        "duration": "5:00",
                        "credits": [{"role": "Remix", "name": "DJ Madd"}],
                    }
                ],
                created_at=datetime(2026, 6, 21, tzinfo=UTC),
                updated_at=datetime(2026, 6, 21, tzinfo=UTC),
            )

    manual_repository = ManualReleaseRepositoryStub()
    app.dependency_overrides[get_manual_release_repository] = lambda: manual_repository
    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/releases/manual-release-1")
    finally:
        app.dependency_overrides.pop(get_manual_release_repository, None)

    assert response.status_code == 200
    assert response.json() == {
        "id": "manual-release-1",
        "discogs_release_id": 0,
        "artist": "KarmaTest",
        "title": "KarmaTestTitle",
        "year": 1998,
        "format": "Vinyl",
        "label": "KarmaTestLabel",
        "catalog_number": "KarmaTest01",
        "barcode": None,
        "genres": ["Electronic"],
        "styles": ["Techno"],
        "thumbnail_url": None,
        "cover_image_url": None,
        "in_collection": True,
        "collection_added_at": "2026-06-21T00:00:00Z",
        "collection_removed_at": None,
        "last_discogs_sync_at": None,
        "discogs_instance_id": None,
        "is_favorite": False,
        "has_full_discogs_info": False,
        "available_sides": [],
        "available_side_options": [],
        "tracklist": [
            {
                "position": "1",
                "title": "KarmaTestTrack",
                "duration": "5:00",
                "artists": [],
                "extra_artists": [{"name": "DJ Madd", "role": "Remix"}],
            }
        ],
        "discogs_artists": [],
        "created_at": "2026-06-21T00:00:00Z",
        "updated_at": "2026-06-21T00:00:00Z",
    }
    assert service.lookup_calls == ["manual-release-1"]
    assert manual_repository.lookup_calls == [("manual-release-1", "test-user")]


def test_get_release_endpoint_derives_manual_side_options_from_prefixed_tracks(
    build_stub_release_import_service,
    override_release_import_service,
) -> None:
    service = build_stub_release_import_service()
    override_release_import_service(service)
    manual_release = _manual_release_stub()
    manual_release.tracklist = [
        {"position": "A1", "title": "Open", "duration": None, "credits": []},
        {"position": "A2", "title": "Build", "duration": None, "credits": []},
        {"position": "B1", "title": "Flip", "duration": None, "credits": []},
    ]
    manual_repository = ManualReleaseRepositoryStub(manual_release)
    app.dependency_overrides[get_manual_release_repository] = lambda: manual_repository
    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/releases/manual-release-1")
    finally:
        app.dependency_overrides.pop(get_manual_release_repository, None)

    assert response.status_code == 200
    assert response.json()["available_sides"] == ["A", "B"]
    assert response.json()["available_side_options"] == [
        {"value": "A", "label": "Side A", "side": "A", "disc_number": None},
        {"value": "B", "label": "Side B", "side": "B", "disc_number": None},
    ]


def test_update_release_favorite_endpoint_updates_release(
    build_stub_release_import_service,
    override_release_import_service,
) -> None:
    service = build_stub_release_import_service()
    override_release_import_service(service)
    app.dependency_overrides[get_releases_repository] = lambda: service

    with TestClient(app) as client:
        response = client.patch("/api/v1/releases/release-123/favorite", json={"is_favorite": True})

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["is_favorite"] is True
    assert service.favorite_calls == [("release-123", True)]


def test_update_release_favorite_endpoint_updates_manual_release(
    build_stub_release_import_service,
    override_release_import_service,
) -> None:
    service = build_stub_release_import_service()
    override_release_import_service(service)
    manual_repository = ManualReleaseRepositoryStub()
    app.dependency_overrides[get_releases_repository] = lambda: service
    app.dependency_overrides[get_manual_release_repository] = lambda: manual_repository

    with TestClient(app) as client:
        response = client.patch("/api/v1/releases/manual-release-1/favorite", json={"is_favorite": True})

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["id"] == "manual-release-1"
    assert response.json()["is_favorite"] is True
    assert service.lookup_calls == ["manual-release-1"]
    assert manual_repository.lookup_calls == [("manual-release-1", "test-user")]
    assert manual_repository.favorite_calls == [("manual-release-1", True)]


def test_deactivate_release_collection_membership_endpoint_preserves_release(
    build_stub_release_import_service,
    override_release_import_service,
) -> None:
    service = build_stub_release_import_service()
    service.release.in_collection = True
    service.release.collection_added_at = datetime(2026, 6, 1, tzinfo=UTC)
    override_release_import_service(service)
    app.dependency_overrides[get_releases_repository] = lambda: service

    with TestClient(app) as client:
        response = client.post("/api/v1/releases/release-123/collection/deactivate")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["id"] == "release-123"
    assert response.json()["in_collection"] is False
    assert response.json()["collection_removed_at"] is not None
    assert service.deactivate_calls == ["release-123"]


def test_deactivate_release_collection_membership_endpoint_supports_manual_release(
    build_stub_release_import_service,
    override_release_import_service,
) -> None:
    service = build_stub_release_import_service()
    override_release_import_service(service)
    manual_repository = ManualReleaseRepositoryStub()
    app.dependency_overrides[get_releases_repository] = lambda: service
    app.dependency_overrides[get_manual_release_repository] = lambda: manual_repository

    with TestClient(app) as client:
        response = client.post("/api/v1/releases/manual-release-1/collection/deactivate")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["id"] == "manual-release-1"
    assert response.json()["in_collection"] is False
    assert response.json()["collection_removed_at"] is not None
    assert service.lookup_calls == ["manual-release-1"]
    assert manual_repository.lookup_calls == [("manual-release-1", "test-user")]
    assert manual_repository.deactivate_calls == ["manual-release-1"]


def test_reactivate_release_collection_membership_endpoint_restores_existing_release(
    build_stub_release_import_service,
    override_release_import_service,
) -> None:
    service = build_stub_release_import_service()
    service.release.in_collection = False
    service.release.collection_removed_at = datetime(2026, 6, 1, tzinfo=UTC)
    override_release_import_service(service)
    app.dependency_overrides[get_releases_repository] = lambda: service

    with TestClient(app) as client:
        response = client.post("/api/v1/releases/release-123/collection/reactivate")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["id"] == "release-123"
    assert response.json()["in_collection"] is True
    assert response.json()["collection_added_at"] is not None
    assert response.json()["collection_removed_at"] is None
    assert service.reactivate_calls == ["release-123"]


def test_reactivate_release_collection_membership_endpoint_supports_manual_release(
    build_stub_release_import_service,
    override_release_import_service,
) -> None:
    service = build_stub_release_import_service()
    override_release_import_service(service)
    manual_release = _manual_release_stub()
    manual_release.in_collection = False
    manual_release.collection_removed_at = datetime(2026, 6, 1, tzinfo=UTC)
    manual_repository = ManualReleaseRepositoryStub(manual_release)
    app.dependency_overrides[get_releases_repository] = lambda: service
    app.dependency_overrides[get_manual_release_repository] = lambda: manual_repository

    with TestClient(app) as client:
        response = client.post("/api/v1/releases/manual-release-1/collection/reactivate")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["id"] == "manual-release-1"
    assert response.json()["in_collection"] is True
    assert response.json()["collection_added_at"] is not None
    assert response.json()["collection_removed_at"] is None
    assert service.lookup_calls == ["manual-release-1"]
    assert manual_repository.lookup_calls == [("manual-release-1", "test-user")]
    assert manual_repository.reactivate_calls == ["manual-release-1"]


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

    class EmptyManualReleaseRepositoryStub:
        def get_release(self, _db, release_id: str, *, user_id: str):
            _ = (release_id, user_id)
            return

    app.dependency_overrides[get_manual_release_repository] = lambda: EmptyManualReleaseRepositoryStub()
    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/releases/missing-release")
    finally:
        app.dependency_overrides.pop(get_manual_release_repository, None)

    assert response.status_code == 404
    assert response.json() == {"detail": "Release 'missing-release' was not found."}


def test_get_release_flow_insights_endpoint_returns_record_flow_summary(
    build_stub_sessions_service,
    override_sessions_service,
) -> None:
    service = build_stub_sessions_service()
    override_sessions_service(service)

    with TestClient(app) as client:
        response = client.get("/api/v1/releases/release-123/flow-insights", params={"limit": 3, "period": "6m"})

    assert response.status_code == 200
    assert response.json() == {
        "release_id": "release-123",
        "before": [
            {
                "release_id": "release-before",
                "artist": "Aphex Twin",
                "title": "Selected Ambient Works 85-92",
                "year": 1992,
                "thumbnail_url": None,
                "cover_image_url": "https://img.discogs.com/before.jpg",
                "styles": ["Ambient"],
                "count": 2,
            }
        ],
        "after": [
            {
                "release_id": "release-after",
                "artist": "Basic Channel",
                "title": "Quadrant Dub",
                "year": 1994,
                "thumbnail_url": None,
                "cover_image_url": "https://img.discogs.com/after.jpg",
                "styles": ["Dub Techno"],
                "count": 1,
            }
        ],
        "mood_transitions": [
            {
                "previous_mood": "Calm",
                "current_mood": "Focused",
                "next_mood": "Energetic",
                "count": 1,
            }
        ],
        "sample_size": 2,
        "confidence": "low",
    }
    assert service.flow_calls == [("release-123", 3, "6m")]


def test_get_release_flow_insights_endpoint_passes_manual_release_to_service(
    build_stub_sessions_service,
    override_sessions_service,
) -> None:
    service = build_stub_sessions_service()
    service.flow_insights = service.flow_insights.__class__(
        release_id="manual-release-1",
        before=service.flow_insights.before,
        after=service.flow_insights.after,
        mood_transitions=service.flow_insights.mood_transitions,
        sample_size=service.flow_insights.sample_size,
        confidence=service.flow_insights.confidence,
    )
    override_sessions_service(service)

    with TestClient(app) as client:
        response = client.get("/api/v1/releases/manual-release-1/flow-insights")

    assert response.status_code == 200
    assert response.json()["release_id"] == "manual-release-1"
    assert response.json()["before"]
    assert response.json()["after"]
    assert response.json()["mood_transitions"]
    assert service.flow_calls == [("manual-release-1", 5, "3m")]
    assert service.user_id_calls == ["test-user"]


def test_get_release_sessions_endpoint_returns_manual_release_sessions(
    build_stub_sessions_service,
    override_sessions_service,
) -> None:
    service = build_stub_sessions_service()
    service.release_sessions = [
        SessionStub(
            id="manual-session-1",
            release_id=None,
            manual_release_id="manual-release-1",
            rating=5,
            mood="Focused",
            notes=None,
            played_at=datetime(2026, 3, 14, 19, 21, tzinfo=UTC),
            vinyl_side=None,
            created_at=datetime(2026, 4, 19, 8, 30, tzinfo=UTC),
        )
    ]
    service.tracks_by_session_id = {
        "manual-session-1": [
            SimpleNamespace(
                track_position="1",
                track_artist=None,
                track_title="Manual Track",
                track_duration="5:08",
                track_sequence=1,
            )
        ]
    }
    override_sessions_service(service)

    with TestClient(app) as client:
        response = client.get("/api/v1/releases/manual-release-1/sessions")

    assert response.status_code == 200
    assert response.json()["sessions"][0]["session_id"] == "manual-session-1"
    assert response.json()["sessions"][0]["tracks"][0]["position"] == "1"
    assert service.list_calls == [("manual-release-1", 20, 0)]
