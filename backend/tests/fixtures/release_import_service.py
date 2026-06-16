from collections.abc import Callable
from datetime import UTC, datetime

import pytest

from app.models.releases import Releases
from app.services.release_import_service import ReleaseImportService


class StubDiscogsService:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.calls: list[tuple[int, bool]] = []

    def fetch_release(self, _db, discogs_release_id: int, *, force_refresh: bool = False) -> dict:
        self.calls.append((discogs_release_id, force_refresh))
        return self.payload


class InMemoryReleasesRepository:
    def __init__(self, release: Releases | None = None) -> None:
        self.release = release
        self.saved_payloads: list[tuple[int, str]] = []

    def get_by_id(self, _db, release_id: str) -> Releases | None:
        if self.release and self.release.id == release_id:
            return self.release
        return None

    def get_by_discogs_release_id(self, _db, discogs_release_id: int) -> Releases | None:
        if self.release and self.release.discogs_release_id == discogs_release_id:
            return self.release
        return None

    def save_or_update(self, _db, data) -> tuple[Releases, bool]:
        created = self.release is None
        if self.release is None:
            self.release = Releases(
                id="release-123",
                discogs_release_id=data.discogs_release_id,
                artist=data.artist,
                title=data.title,
                year=data.year,
                label=data.label,
                catalog_number=data.catalog_number,
                barcode=data.barcode,
                genres=data.genres,
                styles=data.styles,
                cover_image_url=data.cover_image_url,
                created_at=datetime(2026, 4, 19, tzinfo=UTC),
                updated_at=datetime(2026, 4, 19, tzinfo=UTC),
            )
        else:
            self.release.artist = data.artist
            self.release.title = data.title
            self.release.year = data.year
            self.release.label = data.label
            self.release.catalog_number = data.catalog_number
            self.release.barcode = data.barcode
            self.release.genres = data.genres
            self.release.styles = data.styles
            self.release.cover_image_url = data.cover_image_url
            self.release.updated_at = datetime(2026, 4, 20, tzinfo=UTC)

        self.saved_payloads.append((data.discogs_release_id, data.title))
        return self.release, created


class InMemoryDiscogsReleaseRepository:
    def __init__(self, raw_discogs_json: dict | None = None) -> None:
        self.raw_discogs_json = raw_discogs_json
        self.upsert_calls: list[tuple[int, dict]] = []

    def get_by_discogs_release_id(self, _db, _discogs_release_id: int):
        if self.raw_discogs_json is None:
            return None

        class CacheEntry:
            def __init__(self, raw_discogs_json: dict) -> None:
                self.raw_discogs_json = raw_discogs_json

        return CacheEntry(self.raw_discogs_json)

    def upsert(self, _db, discogs_release_id: int, raw_discogs_json: dict):
        self.raw_discogs_json = raw_discogs_json
        self.upsert_calls.append((discogs_release_id, raw_discogs_json))

        class CacheEntry:
            def __init__(self, raw_discogs_json: dict) -> None:
                self.raw_discogs_json = raw_discogs_json

        return CacheEntry(raw_discogs_json)


@pytest.fixture
def discogs_release_payload() -> dict:
    return {
        "id": 555123,
        "artists_sort": "Boards of Canada",
        "title": "Music Has The Right To Children",
        "thumb": "https://img.discogs.com/thumb.jpg",
        "genres": ["Electronic"],
        "styles": ["IDM"],
    }


@pytest.fixture
def release_import_discogs_service_factory() -> Callable[[dict], StubDiscogsService]:
    def _factory(payload: dict) -> StubDiscogsService:
        return StubDiscogsService(payload)

    return _factory


@pytest.fixture
def release_import_repository_factory() -> Callable[[Releases | None], InMemoryReleasesRepository]:
    def _factory(release: Releases | None = None) -> InMemoryReleasesRepository:
        return InMemoryReleasesRepository(release=release)

    return _factory


@pytest.fixture
def release_import_discogs_repository_factory() -> Callable[[dict | None], InMemoryDiscogsReleaseRepository]:
    def _factory(raw_discogs_json: dict | None = None) -> InMemoryDiscogsReleaseRepository:
        return InMemoryDiscogsReleaseRepository(raw_discogs_json=raw_discogs_json)

    return _factory


@pytest.fixture
def build_release_import_service() -> Callable[..., ReleaseImportService]:
    def _build_service(
        *,
        discogs_service: StubDiscogsService | None = None,
        repository: InMemoryReleasesRepository | None = None,
        discogs_repository: InMemoryDiscogsReleaseRepository | None = None,
    ) -> ReleaseImportService:
        return ReleaseImportService(
            discogs_service=discogs_service or StubDiscogsService({}),
            repository=repository or InMemoryReleasesRepository(),
            discogs_repository=discogs_repository or InMemoryDiscogsReleaseRepository(),
        )

    return _build_service
