from datetime import UTC, datetime

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


def test_import_release_creates_a_new_internal_release() -> None:
    discogs_service = StubDiscogsService(
        {
            "id": 555123,
            "artists_sort": "Boards of Canada",
            "title": "Music Has The Right To Children",
            "genres": ["Electronic"],
            "styles": ["IDM"],
        }
    )
    repository = InMemoryReleasesRepository()
    service = ReleaseImportService(discogs_service=discogs_service, repository=repository)

    result = service.import_release(db=object(), discogs_release_id=555123)

    assert result.created is True
    assert result.status == "created"
    assert result.release.id == "release-123"
    assert result.release.discogs_release_id == 555123
    assert discogs_service.calls == [(555123, False)]


def test_import_release_updates_existing_release_when_present() -> None:
    existing_release = Releases(
        id="release-123",
        discogs_release_id=555123,
        artist="Old Artist",
        title="Old Title",
        year=1990,
        label=None,
        catalog_number=None,
        barcode=None,
        genres=None,
        styles=None,
        cover_image_url=None,
        created_at=datetime(2026, 4, 18, tzinfo=UTC),
        updated_at=datetime(2026, 4, 18, tzinfo=UTC),
    )
    discogs_service = StubDiscogsService(
        {
            "id": 555123,
            "artists_sort": "Boards of Canada",
            "title": "Music Has The Right To Children",
            "genres": ["Electronic"],
            "styles": ["IDM"],
        }
    )
    repository = InMemoryReleasesRepository(release=existing_release)
    service = ReleaseImportService(discogs_service=discogs_service, repository=repository)

    result = service.import_release(db=object(), discogs_release_id=555123, force_refresh=True)

    assert result.created is False
    assert result.status == "updated"
    assert result.release.id == "release-123"
    assert result.release.artist == "Boards of Canada"
    assert result.release.title == "Music Has The Right To Children"
    assert discogs_service.calls == [(555123, True)]


def test_get_release_returns_repository_result() -> None:
    release = Releases(
        id="release-123",
        discogs_release_id=555123,
        artist="Boards of Canada",
        title="Music Has The Right To Children",
        year=1998,
        label="Warp Records",
        catalog_number="WARPLP55",
        barcode=None,
        genres=["Electronic"],
        styles=["IDM"],
        cover_image_url=None,
        created_at=datetime(2026, 4, 18, tzinfo=UTC),
        updated_at=datetime(2026, 4, 18, tzinfo=UTC),
    )
    repository = InMemoryReleasesRepository(release=release)
    service = ReleaseImportService(discogs_service=StubDiscogsService({}), repository=repository)

    result = service.get_release(db=object(), release_id="release-123")

    assert result is release
