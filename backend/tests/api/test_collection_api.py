from datetime import UTC, datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api.routes.collection import (
    get_collection_folders_repository,
    get_collection_settings_repository,
    get_collection_sync_job_service,
    get_provider_integration_repository,
    get_releases_repository,
)
from app.database.session import get_db
from app.main import app
from app.schemas.collection import CollectionSourceOfTruth, CollectionSyncJobStatusResponse
from app.services.collection_sync_job_service import CollectionSyncConfigurationError, CollectionSyncJobNotFoundError


class StubCollectionSyncJobService:
    def __init__(self) -> None:
        self.processed_job_ids: list[str] = []
        self.create_error: Exception | None = None
        self.get_error: Exception | None = None
        self.active_job: CollectionSyncJobStatusResponse | None = None

    def create_job(self, _db) -> CollectionSyncJobStatusResponse:
        if self.create_error is not None:
            raise self.create_error
        return _job_response()

    def get_job(self, _db, _job_id: str) -> CollectionSyncJobStatusResponse:
        if self.get_error is not None:
            raise self.get_error
        return _job_response(status="running", step="fetching", message="Fetching collection data")

    def get_active_job(self, _db) -> CollectionSyncJobStatusResponse | None:
        return self.active_job

    def process_job(self, job_id: str) -> None:
        self.processed_job_ids.append(job_id)


class StubReleasesRepository:
    def __init__(self, releases: list[SimpleNamespace]) -> None:
        self.releases = releases
        self.calls: list[dict] = []

    def list_collection_releases(
        self,
        _db,
        *,
        limit: int,
        offset: int,
        include_removed: bool = False,
        artist: str | None = None,
        label: str | None = None,
        favorite: bool = False,
        folder_id: int | None = None,
    ):
        self.calls.append(
            {
                "limit": limit,
                "offset": offset,
                "include_removed": include_removed,
                "artist": artist,
                "label": label,
                "favorite": favorite,
                "folder_id": folder_id,
            }
        )
        releases = self._filtered_releases(label=label, favorite=favorite, folder_id=folder_id)
        return releases[offset : offset + limit]

    def count_collection_releases(
        self,
        _db,
        *,
        include_removed: bool = False,
        artist: str | None = None,
        label: str | None = None,
        favorite: bool = False,
        folder_id: int | None = None,
    ) -> int:
        _ = include_removed, artist
        return len(self._filtered_releases(label=label, favorite=favorite, folder_id=folder_id))

    def has_favorite_collection_releases(self, _db) -> bool:
        return any(release.in_collection and release.is_favorite for release in self.releases)

    def _filtered_releases(
        self,
        *,
        label: str | None,
        favorite: bool,
        folder_id: int | None,
    ) -> list[SimpleNamespace]:
        releases = [release for release in self.releases if release.is_favorite] if favorite else self.releases
        if label is not None:
            releases = [release for release in releases if release.label == label]
        if folder_id is not None:
            releases = [
                release
                for release in releases
                if release.in_collection and folder_id in getattr(release, "folder_ids", [])
            ]
        return releases

    def search_collection_releases(
        self,
        _db,
        *,
        artist: str | None = None,
        title: str | None = None,
        catalog: str | None = None,
        barcode: str | None = None,
        year: int | None = None,
        limit: int,
        offset: int,
    ):
        self.calls.append(
            {
                "artist": artist,
                "title": title,
                "catalog": catalog,
                "barcode": barcode,
                "year": year,
                "limit": limit,
                "offset": offset,
            }
        )
        return self.releases[offset : offset + limit]


class StubCollectionSettingsRepository:
    def __init__(self, source_of_truth: CollectionSourceOfTruth = CollectionSourceOfTruth.APP) -> None:
        self.source_of_truth = source_of_truth
        self.update_calls: list[tuple[CollectionSourceOfTruth, str | None]] = []
        self.get_user_ids: list[str | None] = []

    def get_or_create(self, _db, *, user_id: str | None = None):
        self.get_user_ids.append(user_id)
        return SimpleNamespace(source_of_truth=self.source_of_truth)

    def set_source_of_truth(self, _db, source_of_truth: CollectionSourceOfTruth, *, user_id: str | None = None):
        self.update_calls.append((source_of_truth, user_id))
        self.source_of_truth = source_of_truth
        return SimpleNamespace(source_of_truth=source_of_truth)


class StubCollectionFoldersRepository:
    def __init__(self, folders: list[SimpleNamespace]) -> None:
        self.folders = folders

    def list_folders(self, _db):
        return self.folders


class StubProviderIntegrationRepository:
    def __init__(self, *, has_saved_token: bool) -> None:
        self.has_saved_token = has_saved_token
        self.user_ids: list[str | None] = []

    def get_discogs(self, _db, *, user_id: str | None = None):
        self.user_ids.append(user_id)
        if not self.has_saved_token:
            return None
        return SimpleNamespace(
            is_active=True,
            access_token_ciphertext="encrypted-token",
            external_user_id="123",
            external_username="alex",
        )


def test_get_collection_settings_defaults_to_app_source_of_truth() -> None:
    repository = StubCollectionSettingsRepository()
    _override_db()
    app.dependency_overrides[get_collection_settings_repository] = lambda: repository

    with TestClient(app) as client:
        response = client.get("/api/v1/collection/settings")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"source_of_truth": "APP"}
    assert repository.get_user_ids == ["test-user"]


def test_update_collection_settings_persists_discogs_source_of_truth() -> None:
    repository = StubCollectionSettingsRepository()
    integration_repository = StubProviderIntegrationRepository(has_saved_token=True)
    _override_db()
    app.dependency_overrides[get_collection_settings_repository] = lambda: repository
    app.dependency_overrides[get_provider_integration_repository] = lambda: integration_repository

    with TestClient(app) as client:
        response = client.put("/api/v1/collection/settings", json={"source_of_truth": "DISCOGS"})

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"source_of_truth": "DISCOGS"}
    assert repository.update_calls == [(CollectionSourceOfTruth.DISCOGS, "test-user")]
    assert integration_repository.user_ids == ["test-user"]


def test_update_collection_settings_rejects_discogs_without_saved_token() -> None:
    repository = StubCollectionSettingsRepository()
    integration_repository = StubProviderIntegrationRepository(has_saved_token=False)
    _override_db()
    app.dependency_overrides[get_collection_settings_repository] = lambda: repository
    app.dependency_overrides[get_provider_integration_repository] = lambda: integration_repository

    with TestClient(app) as client:
        response = client.put("/api/v1/collection/settings", json={"source_of_truth": "DISCOGS"})

    app.dependency_overrides.clear()

    assert response.status_code == 400
    assert response.json() == {
        "error": {
            "code": "discogs_token_required",
            "message": "Discogs access token is required before using Discogs as source of truth.",
        }
    }
    assert repository.update_calls == []
    assert integration_repository.user_ids == ["test-user"]


def test_update_collection_settings_rejects_unknown_source_of_truth() -> None:
    repository = StubCollectionSettingsRepository()
    _override_db()
    app.dependency_overrides[get_collection_settings_repository] = lambda: repository

    with TestClient(app) as client:
        response = client.put("/api/v1/collection/settings", json={"source_of_truth": "LOCAL"})

    app.dependency_overrides.clear()

    assert response.status_code == 422
    assert repository.update_calls == []


def test_list_collection_folders_returns_not_configured_without_discogs_token() -> None:
    folder_repository = StubCollectionFoldersRepository([_folder(0, "All", is_default=True)])
    integration_repository = StubProviderIntegrationRepository(has_saved_token=False)
    _override_db()
    app.dependency_overrides[get_collection_folders_repository] = lambda: folder_repository
    app.dependency_overrides[get_provider_integration_repository] = lambda: integration_repository

    with TestClient(app) as client:
        response = client.get("/api/v1/collection/folders")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"discogs_configured": False, "folders": [], "has_extra_folders": False}
    assert integration_repository.user_ids == ["test-user"]


def test_list_collection_folders_returns_configured_folders() -> None:
    folder_repository = StubCollectionFoldersRepository(
        [
            _folder(0, "All", count=3, is_default=True),
            _folder(123, "Shelf A", count=2),
        ]
    )
    integration_repository = StubProviderIntegrationRepository(has_saved_token=True)
    _override_db()
    app.dependency_overrides[get_collection_folders_repository] = lambda: folder_repository
    app.dependency_overrides[get_provider_integration_repository] = lambda: integration_repository

    with TestClient(app) as client:
        response = client.get("/api/v1/collection/folders")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "discogs_configured": True,
        "folders": [
            {"id": 0, "name": "All", "count": 3, "is_default": True},
            {"id": 123, "name": "Shelf A", "count": 2, "is_default": False},
        ],
        "has_extra_folders": True,
    }
    assert integration_repository.user_ids == ["test-user"]


def test_create_collection_sync_job_returns_accepted_status() -> None:
    service = StubCollectionSyncJobService()
    _override_db()
    app.dependency_overrides[get_collection_sync_job_service] = lambda: service

    with TestClient(app) as client:
        response = client.post("/api/v1/collection/sync")

    app.dependency_overrides.clear()

    assert response.status_code == 202
    assert response.json()["job_id"] == "job-123"
    assert response.json()["status"] == "queued"
    assert service.processed_job_ids == ["job-123"]


def test_create_collection_sync_job_returns_config_error() -> None:
    service = StubCollectionSyncJobService()
    service.create_error = CollectionSyncConfigurationError()
    _override_db()
    app.dependency_overrides[get_collection_sync_job_service] = lambda: service

    with TestClient(app) as client:
        response = client.post("/api/v1/collection/sync")

    app.dependency_overrides.clear()

    assert response.status_code == 500
    assert response.json() == {
        "error": {
            "code": "discogs_config_missing",
            "message": "Discogs collection sync is not configured.",
        }
    }
    assert service.processed_job_ids == []


def test_get_collection_sync_job_returns_status() -> None:
    service = StubCollectionSyncJobService()
    _override_db()
    app.dependency_overrides[get_collection_sync_job_service] = lambda: service

    with TestClient(app) as client:
        response = client.get("/api/v1/collection/sync/job-123")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["status"] == "running"
    assert response.json()["step"] == "fetching"
    assert response.json()["message"] == "Fetching collection data"


def test_get_active_collection_sync_job_returns_current_status() -> None:
    service = StubCollectionSyncJobService()
    service.active_job = _job_response(status="running", step="fetching", message="Fetching collection data")
    _override_db()
    app.dependency_overrides[get_collection_sync_job_service] = lambda: service

    with TestClient(app) as client:
        response = client.get("/api/v1/collection/sync/active")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["job_id"] == "job-123"
    assert response.json()["status"] == "running"
    assert response.json()["step"] == "fetching"
    assert response.json()["message"] == "Fetching collection data"


def test_get_active_collection_sync_job_returns_no_content_when_idle() -> None:
    service = StubCollectionSyncJobService()
    _override_db()
    app.dependency_overrides[get_collection_sync_job_service] = lambda: service

    with TestClient(app) as client:
        response = client.get("/api/v1/collection/sync/active")

    app.dependency_overrides.clear()

    assert response.status_code == 204
    assert response.content == b""


def test_get_collection_sync_job_returns_not_found() -> None:
    service = StubCollectionSyncJobService()
    service.get_error = CollectionSyncJobNotFoundError("missing")
    _override_db()
    app.dependency_overrides[get_collection_sync_job_service] = lambda: service

    with TestClient(app) as client:
        response = client.get("/api/v1/collection/sync/missing")

    app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "collection_sync_job_not_found",
            "message": "Collection sync job was not found.",
        }
    }


def test_list_collection_releases_returns_paginated_active_records() -> None:
    releases = [
        _release("release-1", 101, "First"),
        _release("release-2", 202, "Second"),
        _release("release-3", 303, "Third"),
    ]
    repository = StubReleasesRepository(releases)
    _override_db()
    app.dependency_overrides[get_releases_repository] = lambda: repository

    with TestClient(app) as client:
        response = client.get("/api/v1/collection/releases", params={"limit": 2, "offset": 0})

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "items": [
            {
                "id": "release-1",
                "discogs_release_id": 101,
                "title": "First",
                "artist": "Artist",
                "year": 2021,
                "format": "Vinyl, LP",
                "label": "Label",
                "catalog_number": "CAT-1",
                "styles": ["Dub", "Dub Techno"],
                "thumb_url": "https://example.test/thumb.jpg",
                "collection_added_at": "2021-10-05T12:32:40Z",
                "in_collection": True,
                "is_favorite": False,
            },
            {
                "id": "release-2",
                "discogs_release_id": 202,
                "title": "Second",
                "artist": "Artist",
                "year": 2021,
                "format": "Vinyl, LP",
                "label": "Label",
                "catalog_number": "CAT-1",
                "styles": ["Dub", "Dub Techno"],
                "thumb_url": "https://example.test/thumb.jpg",
                "collection_added_at": "2021-10-05T12:32:40Z",
                "in_collection": True,
                "is_favorite": False,
            },
        ],
        "limit": 2,
        "offset": 0,
        "total": 3,
        "has_more": True,
        "has_favorites": False,
    }
    assert repository.calls == [
        {
            "limit": 3,
            "offset": 0,
            "include_removed": False,
            "artist": None,
            "label": None,
            "favorite": False,
            "folder_id": None,
        }
    ]


def test_list_collection_releases_filters_by_artist() -> None:
    repository = StubReleasesRepository([_release("release-1", 101, "First")])
    _override_db()
    app.dependency_overrides[get_releases_repository] = lambda: repository

    with TestClient(app) as client:
        response = client.get("/api/v1/collection/releases", params={"artist": "Basic Channel"})

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["items"][0]["id"] == "release-1"
    assert repository.calls == [
        {
            "limit": 26,
            "offset": 0,
            "include_removed": False,
            "artist": "Basic Channel",
            "label": None,
            "favorite": False,
            "folder_id": None,
        }
    ]


def test_list_collection_releases_filters_by_label() -> None:
    repository = StubReleasesRepository(
        [
            _release("release-1", 101, "First", label="Wackie's"),
            _release("release-2", 202, "Second", label="Other"),
        ]
    )
    _override_db()
    app.dependency_overrides[get_releases_repository] = lambda: repository

    with TestClient(app) as client:
        response = client.get("/api/v1/collection/releases", params={"label": "Wackie's"})

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["items"][0]["id"] == "release-1"
    assert repository.calls == [
        {
            "limit": 26,
            "offset": 0,
            "include_removed": False,
            "artist": None,
            "label": "Wackie's",
            "favorite": False,
            "folder_id": None,
        }
    ]


def test_list_collection_releases_filters_by_favorites() -> None:
    repository = StubReleasesRepository(
        [
            _release("release-1", 101, "Favorite", is_favorite=True),
            _release("release-2", 202, "Regular"),
        ]
    )
    _override_db()
    app.dependency_overrides[get_releases_repository] = lambda: repository

    with TestClient(app) as client:
        response = client.get("/api/v1/collection/releases", params={"favorite": True})

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["has_favorites"] is True
    assert response.json()["items"][0]["is_favorite"] is True
    assert repository.calls == [
        {
            "limit": 26,
            "offset": 0,
            "include_removed": False,
            "artist": None,
            "label": None,
            "favorite": True,
            "folder_id": None,
        }
    ]


def test_list_collection_releases_filters_by_folder() -> None:
    repository = StubReleasesRepository(
        [
            _release("release-1", 101, "Shelf A", folder_ids=[123]),
            _release("release-2", 202, "Shelf B", folder_ids=[456]),
            _release("release-3", 303, "Removed Shelf A", in_collection=False, folder_ids=[123]),
        ]
    )
    _override_db()
    app.dependency_overrides[get_releases_repository] = lambda: repository

    with TestClient(app) as client:
        response = client.get("/api/v1/collection/releases", params={"folder_id": 123})

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert [item["id"] for item in response.json()["items"]] == ["release-1"]
    assert response.json()["total"] == 1
    assert repository.calls == [
        {
            "limit": 26,
            "offset": 0,
            "include_removed": False,
            "artist": None,
            "label": None,
            "favorite": False,
            "folder_id": 123,
        }
    ]


def test_list_collection_releases_rejects_oversized_artist_filter() -> None:
    repository = StubReleasesRepository([])
    _override_db()
    app.dependency_overrides[get_releases_repository] = lambda: repository

    with TestClient(app) as client:
        response = client.get("/api/v1/collection/releases", params={"artist": "a" * 256})

    app.dependency_overrides.clear()

    assert response.status_code == 422
    assert repository.calls == []


def test_list_collection_releases_rejects_oversized_label_filter() -> None:
    repository = StubReleasesRepository([])
    _override_db()
    app.dependency_overrides[get_releases_repository] = lambda: repository

    with TestClient(app) as client:
        response = client.get("/api/v1/collection/releases", params={"label": "a" * 256})

    app.dependency_overrides.clear()

    assert response.status_code == 422
    assert repository.calls == []


def test_list_collection_releases_accepts_custom_max_limit() -> None:
    repository = StubReleasesRepository([])
    _override_db()
    app.dependency_overrides[get_releases_repository] = lambda: repository

    with TestClient(app) as client:
        response = client.get("/api/v1/collection/releases", params={"limit": 250, "offset": 0})

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "items": [],
        "limit": 250,
        "offset": 0,
        "total": 0,
        "has_more": False,
        "has_favorites": False,
    }
    assert repository.calls == [
        {
            "limit": 251,
            "offset": 0,
            "include_removed": False,
            "artist": None,
            "label": None,
            "favorite": False,
            "folder_id": None,
        }
    ]


def test_search_collection_releases_rejects_oversized_artist_filter() -> None:
    repository = StubReleasesRepository([])
    _override_db()
    app.dependency_overrides[get_releases_repository] = lambda: repository

    with TestClient(app) as client:
        response = client.get("/api/v1/collection/search", params={"artist": "a" * 256})

    app.dependency_overrides.clear()

    assert response.status_code == 422
    assert repository.calls == []


def test_search_collection_releases_returns_internal_release_results() -> None:
    repository = StubReleasesRepository([_release("release-1", 101, "First")])
    _override_db()
    app.dependency_overrides[get_releases_repository] = lambda: repository

    with TestClient(app) as client:
        response = client.get(
            "/api/v1/collection/search",
            params={"artist": "Artist", "catalog": "CAT", "limit": 10, "offset": 0},
        )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "results": [
            {
                "release_id": "release-1",
                "discogs_release_id": 101,
                "artist": "Artist",
                "title": "First",
                "year": 2021,
                "label": "Label",
                "catalog_number": "CAT-1",
                "thumbnail_url": "https://example.test/cover.jpg",
                "format": "Vinyl, LP",
            }
        ],
        "limit": 10,
        "offset": 0,
        "has_more": False,
    }
    assert repository.calls == [
        {
            "artist": "Artist",
            "title": None,
            "catalog": "CAT",
            "barcode": None,
            "year": None,
            "limit": 11,
            "offset": 0,
        }
    ]


def test_search_collection_releases_reports_has_more() -> None:
    repository = StubReleasesRepository(
        [
            _release("release-1", 101, "First"),
            _release("release-2", 102, "Second"),
            _release("release-3", 103, "Third"),
        ]
    )
    _override_db()
    app.dependency_overrides[get_releases_repository] = lambda: repository

    with TestClient(app) as client:
        response = client.get(
            "/api/v1/collection/search",
            params={"artist": "Artist", "limit": 2, "offset": 0},
        )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert [item["release_id"] for item in response.json()["results"]] == ["release-1", "release-2"]
    assert response.json()["limit"] == 2
    assert response.json()["offset"] == 0
    assert response.json()["has_more"] is True
    assert repository.calls == [
        {
            "artist": "Artist",
            "title": None,
            "catalog": None,
            "barcode": None,
            "year": None,
            "limit": 3,
            "offset": 0,
        }
    ]


def _override_db() -> None:
    def _fake_db():
        yield object()

    app.dependency_overrides[get_db] = _fake_db


def _job_response(
    *,
    status: str = "queued",
    step: str | None = None,
    message: str = "Collection sync queued",
) -> CollectionSyncJobStatusResponse:
    now = datetime(2026, 6, 4, 12, 0, tzinfo=UTC)
    return CollectionSyncJobStatusResponse(
        job_id="job-123",
        status=status,
        step=step,
        message=message,
        created_at=now,
        updated_at=now,
    )


def _release(
    release_id: str,
    discogs_release_id: int,
    title: str,
    *,
    is_favorite: bool = False,
    in_collection: bool = True,
    label: str = "Label",
    folder_ids: list[int] | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=release_id,
        discogs_release_id=discogs_release_id,
        title=title,
        artist="Artist",
        year=2021,
        format="Vinyl, LP",
        label=label,
        catalog_number="CAT-1",
        styles=["Dub", "Dub Techno"],
        thumbnail_url="https://example.test/thumb.jpg",
        cover_image_url="https://example.test/cover.jpg",
        collection_added_at=datetime(2021, 10, 5, 12, 32, 40, tzinfo=UTC),
        in_collection=in_collection,
        is_favorite=is_favorite,
        folder_ids=folder_ids or [],
    )


def _folder(
    folder_id: int,
    name: str,
    *,
    count: int | None = None,
    is_default: bool = False,
) -> SimpleNamespace:
    return SimpleNamespace(
        discogs_folder_id=folder_id,
        name=name,
        item_count=count,
        is_default=is_default,
    )
