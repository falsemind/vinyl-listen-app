from datetime import UTC, datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api.routes.collection import get_collection_sync_job_service, get_releases_repository
from app.database.session import get_db
from app.main import app
from app.schemas.collection import CollectionSyncJobStatusResponse
from app.services.collection_sync_job_service import CollectionSyncConfigurationError, CollectionSyncJobNotFoundError


class StubCollectionSyncJobService:
    def __init__(self) -> None:
        self.processed_job_ids: list[str] = []
        self.create_error: Exception | None = None
        self.get_error: Exception | None = None

    def create_job(self, _db) -> CollectionSyncJobStatusResponse:
        if self.create_error is not None:
            raise self.create_error
        return _job_response()

    def get_job(self, _db, _job_id: str) -> CollectionSyncJobStatusResponse:
        if self.get_error is not None:
            raise self.get_error
        return _job_response(status="running", step="fetching", message="Fetching collection data")

    def process_job(self, job_id: str) -> None:
        self.processed_job_ids.append(job_id)


class StubReleasesRepository:
    def __init__(self, releases: list[SimpleNamespace]) -> None:
        self.releases = releases
        self.calls: list[dict] = []

    def list_collection_releases(self, _db, *, limit: int, offset: int, include_removed: bool = False):
        self.calls.append({"limit": limit, "offset": offset, "include_removed": include_removed})
        return self.releases[offset : offset + limit]


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
            },
        ],
        "limit": 2,
        "offset": 0,
        "has_more": True,
    }
    assert repository.calls == [{"limit": 3, "offset": 0, "include_removed": False}]


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


def _release(release_id: str, discogs_release_id: int, title: str) -> SimpleNamespace:
    return SimpleNamespace(
        id=release_id,
        discogs_release_id=discogs_release_id,
        title=title,
        artist="Artist",
        year=2021,
        format="Vinyl, LP",
        label="Label",
        catalog_number="CAT-1",
        styles=["Dub", "Dub Techno"],
        thumbnail_url="https://example.test/thumb.jpg",
        cover_image_url="https://example.test/cover.jpg",
        collection_added_at=datetime(2021, 10, 5, 12, 32, 40, tzinfo=UTC),
        in_collection=True,
    )
