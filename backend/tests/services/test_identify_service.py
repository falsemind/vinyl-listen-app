from dataclasses import dataclass
from datetime import UTC, datetime

from app.pipelines.identification import ExtractedIdentifiers, IdentifierExtractor, ImageVariant, PreparedImage
from app.services.identify_service import IdentifyService, IdentifyValidationError


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
    def __init__(self, payload: dict | None = None) -> None:
        self.payload = payload or {"results": []}
        self.search_by_barcode_calls: list[tuple[str, int]] = []
        self.search_release_calls: list[dict] = []

    def search_by_barcode(self, barcode: str, *, limit: int = 10) -> dict:
        self.search_by_barcode_calls.append((barcode, limit))
        return self.payload

    def search_releases(self, *, limit: int = 10, **kwargs) -> dict:
        self.search_release_calls.append({"limit": limit, **kwargs})
        return self.payload


def build_release_stub(
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


def test_identify_service_returns_local_match_before_discogs_lookup() -> None:
    repository = StubReleasesRepository(barcode_matches=[build_release_stub()])
    discogs_service = StubDiscogsService(
        payload={"results": [{"id": 999, "title": "Should Not - Be Called", "year": 2000}]}
    )
    service = IdentifyService(
        repository=repository,
        discogs_service=discogs_service,
        image_processor=StubImageProcessor(),
        identifier_extractor=StubIdentifierExtractor(
            ExtractedIdentifiers(barcodes=("724384497818",), catalog_numbers=(), artist=None, title=None)
        ),
    )

    result = service.identify(
        db=object(),
        image_bytes=b"fake-image",
        filename="cover.jpg",
        content_type="image/jpeg",
    )

    assert [candidate.discogs_release_id for candidate in result.candidates] == [123]
    assert result.candidates[0].match_source == "local"
    assert "barcode" in result.candidates[0].matched_on
    assert discogs_service.search_by_barcode_calls == []
    assert discogs_service.search_release_calls == []


def test_identify_service_falls_back_to_discogs_search_in_priority_order() -> None:
    repository = StubReleasesRepository()
    discogs_service = StubDiscogsService(
        payload={
            "results": [
                {
                    "id": 456,
                    "title": "Air - Moon Safari",
                    "year": "1998",
                    "label": ["Source"],
                    "catno": "7243 8 44978 1 8",
                    "cover_image": "https://img.discogs.com/external.jpg",
                }
            ]
        }
    )
    service = IdentifyService(
        repository=repository,
        discogs_service=discogs_service,
        image_processor=StubImageProcessor(),
        identifier_extractor=StubIdentifierExtractor(
            ExtractedIdentifiers(
                barcodes=("724384497818",),
                catalog_numbers=("7243 8 44978 1 8",),
                artist="Air",
                title="Moon Safari",
            )
        ),
    )

    result = service.identify(
        db=object(),
        image_bytes=b"fake-image",
        filename="cover.jpg",
        content_type="image/jpeg",
    )

    assert [candidate.discogs_release_id for candidate in result.candidates] == [456]
    assert result.candidates[0].match_source == "discogs"
    assert result.candidates[0].matched_on == ("catalog_number", "artist", "title")
    assert discogs_service.search_by_barcode_calls == [("724384497818", 5)]
    assert discogs_service.search_release_calls == []


def test_identify_service_rejects_unsupported_image_type() -> None:
    service = IdentifyService()

    try:
        service.identify(
            db=object(),
            image_bytes=b"fake-image",
            filename="cover.gif",
            content_type="image/gif",
        )
    except IdentifyValidationError as error:
        assert error.status_code == 415
        assert error.code == "unsupported_image_type"
        assert error.message == "Unsupported image type. Supported types: image/jpeg, image/png, image/webp."
    else:
        raise AssertionError("Expected IdentifyValidationError for unsupported media type")


def test_identify_service_returns_empty_candidates_when_no_signals_are_available() -> None:
    repository = StubReleasesRepository()
    discogs_service = StubDiscogsService()
    service = IdentifyService(
        repository=repository,
        discogs_service=discogs_service,
        image_processor=StubImageProcessor(),
        identifier_extractor=StubIdentifierExtractor(ExtractedIdentifiers()),
    )

    result = service.identify(
        db=object(),
        image_bytes=b"fake-image",
        filename="cover.png",
        content_type="image/png",
    )

    assert result.candidates == ()
    assert discogs_service.search_by_barcode_calls == []
    assert discogs_service.search_release_calls == []
