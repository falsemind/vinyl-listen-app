from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.api.routes.releases import get_release_import_service
from app.main import app
from app.services.discogs_service import DiscogsClientError
from app.services.release_import_service import ReleaseImportResult


@dataclass
class ReleaseStub:
    id: str
    discogs_release_id: int
    artist: str
    title: str
    year: int | None
    label: str | None
    catalog_number: str | None
    barcode: str | None
    genres: list[str] | None
    styles: list[str] | None
    cover_image_url: str | None
    created_at: datetime
    updated_at: datetime


class StubReleaseImportService:
    def __init__(self) -> None:
        self.release = ReleaseStub(
            id="release-123",
            discogs_release_id=555123,
            artist="Boards of Canada",
            title="Music Has The Right To Children",
            year=1998,
            label="Warp Records",
            catalog_number="WARPLP55",
            barcode="5021603065515",
            genres=["Electronic"],
            styles=["IDM"],
            cover_image_url="https://img.discogs.com/cover.jpg",
            created_at=datetime(2026, 4, 19, tzinfo=UTC),
            updated_at=datetime(2026, 4, 19, tzinfo=UTC),
        )
        self.import_result = ReleaseImportResult(release=self.release, created=True)
        self.import_error: Exception | None = None
        self.import_calls: list[tuple[int, bool]] = []
        self.lookup_calls: list[str] = []

    def import_release(self, _db, discogs_release_id: int, *, force_refresh: bool = False) -> ReleaseImportResult:
        self.import_calls.append((discogs_release_id, force_refresh))
        if self.import_error is not None:
            raise self.import_error
        return self.import_result

    def get_release(self, _db, release_id: str) -> ReleaseStub | None:
        self.lookup_calls.append(release_id)
        if release_id == self.release.id:
            return self.release
        return None


def test_import_release_endpoint_returns_created_release_id() -> None:
    service = StubReleaseImportService()
    app.dependency_overrides[get_release_import_service] = lambda: service

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/releases/import",
            json={"discogs_release_id": 555123},
        )

    app.dependency_overrides.clear()

    assert response.status_code == 201
    assert response.json() == {
        "release_id": "release-123",
        "discogs_release_id": 555123,
        "status": "created",
    }
    assert service.import_calls == [(555123, False)]


def test_import_release_endpoint_returns_404_for_missing_discogs_release() -> None:
    service = StubReleaseImportService()
    service.import_error = DiscogsClientError("Discogs API error (404): release not found")
    app.dependency_overrides[get_release_import_service] = lambda: service

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/releases/import",
            json={"discogs_release_id": 999999},
        )

    app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json() == {"detail": "Discogs API error (404): release not found"}


def test_get_release_endpoint_returns_local_release_metadata() -> None:
    service = StubReleaseImportService()
    app.dependency_overrides[get_release_import_service] = lambda: service

    with TestClient(app) as client:
        response = client.get("/api/v1/releases/release-123")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "id": "release-123",
        "discogs_release_id": 555123,
        "artist": "Boards of Canada",
        "title": "Music Has The Right To Children",
        "year": 1998,
        "label": "Warp Records",
        "catalog_number": "WARPLP55",
        "barcode": "5021603065515",
        "genres": ["Electronic"],
        "styles": ["IDM"],
        "cover_image_url": "https://img.discogs.com/cover.jpg",
        "created_at": "2026-04-19T00:00:00Z",
        "updated_at": "2026-04-19T00:00:00Z",
    }
    assert service.lookup_calls == ["release-123"]


def test_get_release_endpoint_returns_404_when_release_missing() -> None:
    service = StubReleaseImportService()
    app.dependency_overrides[get_release_import_service] = lambda: service

    with TestClient(app) as client:
        response = client.get("/api/v1/releases/missing-release")

    app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json() == {"detail": "Release 'missing-release' was not found."}
