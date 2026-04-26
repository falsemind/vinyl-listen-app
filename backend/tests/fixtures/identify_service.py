from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

from app.pipelines.identification import ExtractedIdentifiers, IdentifierExtractor, ImageVariant, PreparedImage
from app.services.identify_service import IdentifyService


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


class StubIdentifierExtractor(IdentifierExtractor):
    def __init__(self, identifiers: ExtractedIdentifiers) -> None:
        self.identifiers = identifiers

    def extract(self, _prepared_image: PreparedImage) -> ExtractedIdentifiers:
        return self.identifiers


class StubImageProcessor:
    def prepare(self, *, filename: str, content_type: str, data: bytes) -> PreparedImage:
        return PreparedImage(
            filename=filename,
            content_type=content_type,
            data=data,
            size_bytes=len(data),
            digest="digest",
            width=1200,
            height=1200,
            variants=(ImageVariant(name="normalized", data=b"normalized-image"),),
        )


class StubReleasesRepository:
    def __init__(
        self,
        *,
        barcode_matches: list[ReleaseStub] | None = None,
        catalog_matches: list[ReleaseStub] | None = None,
        artist_title_matches: list[ReleaseStub] | None = None,
    ) -> None:
        self.barcode_matches = barcode_matches or []
        self.catalog_matches = catalog_matches or []
        self.artist_title_matches = artist_title_matches or []
        self.barcode_calls: list[str] = []
        self.catalog_calls: list[str] = []
        self.artist_title_calls: list[tuple[str, str, int]] = []

    def get_by_barcode(self, _db, barcode: str) -> list[ReleaseStub]:
        self.barcode_calls.append(barcode)
        return self.barcode_matches

    def get_by_catalog_number(self, _db, catalog_number: str) -> list[ReleaseStub]:
        self.catalog_calls.append(catalog_number)
        return self.catalog_matches

    def search_by_artist_and_title(self, _db, *, artist: str, title: str, limit: int) -> list[ReleaseStub]:
        self.artist_title_calls.append((artist, title, limit))
        return self.artist_title_matches


class StubDiscogsService:
    def __init__(self, payload: dict | None = None, *, payloads: list[dict] | None = None) -> None:
        self.payload = payload or {"results": []}
        self.payloads = payloads or []
        self.search_by_barcode_calls: list[tuple[str, int]] = []
        self.search_release_calls: list[dict] = []

    def search_by_barcode(self, barcode: str, *, limit: int = 10) -> dict:
        self.search_by_barcode_calls.append((barcode, limit))
        return self._next_payload()

    def search_releases(self, *, limit: int = 10, **kwargs) -> dict:
        self.search_release_calls.append({"limit": limit, **kwargs})
        return self._next_payload()

    def _next_payload(self) -> dict:
        if self.payloads:
            return self.payloads.pop(0)
        return self.payload


@pytest.fixture
def build_release_stub() -> Callable[..., ReleaseStub]:
    def _build_release_stub(
        *,
        release_id: str = "release-1",
        discogs_release_id: int = 123,
        artist: str = "Air",
        title: str = "Moon Safari",
        catalog_number: str | None = "7243 8 44978 1 8",
        barcode: str | None = "724384497818",
    ) -> ReleaseStub:
        timestamp = datetime(2026, 4, 20, tzinfo=UTC)
        return ReleaseStub(
            id=release_id,
            discogs_release_id=discogs_release_id,
            artist=artist,
            title=title,
            year=1998,
            label="Source",
            catalog_number=catalog_number,
            barcode=barcode,
            genres=["Electronic"],
            styles=["Downtempo"],
            cover_image_url="https://img.discogs.com/cover.jpg",
            created_at=timestamp,
            updated_at=timestamp,
        )

    return _build_release_stub


@pytest.fixture
def releases_repository_factory() -> Callable[..., StubReleasesRepository]:
    def _factory(
        *,
        barcode_matches: list[ReleaseStub] | None = None,
        catalog_matches: list[ReleaseStub] | None = None,
        artist_title_matches: list[ReleaseStub] | None = None,
    ) -> StubReleasesRepository:
        return StubReleasesRepository(
            barcode_matches=barcode_matches,
            catalog_matches=catalog_matches,
            artist_title_matches=artist_title_matches,
        )

    return _factory


@pytest.fixture
def discogs_service_factory() -> Callable[..., StubDiscogsService]:
    def _factory(payload: dict | None = None, *, payloads: list[dict] | None = None) -> StubDiscogsService:
        return StubDiscogsService(payload=payload, payloads=payloads)

    return _factory


@pytest.fixture
def build_identify_service() -> Callable[..., IdentifyService]:
    def _build_service(
        *,
        repository: StubReleasesRepository | None = None,
        discogs_service: StubDiscogsService | None = None,
        identifiers: ExtractedIdentifiers | None = None,
    ) -> IdentifyService:
        return IdentifyService(
            repository=repository or StubReleasesRepository(),
            discogs_service=discogs_service or StubDiscogsService(),
            image_processor=StubImageProcessor(),
            identifier_extractor=StubIdentifierExtractor(identifiers or ExtractedIdentifiers()),
        )

    return _build_service
