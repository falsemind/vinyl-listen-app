from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import pytest

from app.services.collection_sync_service import CollectionSyncError, CollectionSyncService, collapse_collection_items
from app.services.release_mapper import InternalReleaseData


@dataclass
class FakeRelease:
    discogs_release_id: int
    artist: str
    title: str
    year: int | None
    format: str | None
    label: str | None
    catalog_number: str | None
    barcode: str | None
    genres: list[str] | None
    styles: list[str] | None
    thumbnail_url: str | None
    cover_image_url: str | None
    in_collection: bool = False
    collection_added_at: datetime | None = None
    collection_removed_at: datetime | None = None
    last_discogs_sync_at: datetime | None = None
    discogs_instance_id: int | None = None


class FakeDiscogsService:
    def __init__(self, items: list[dict[str, Any]]) -> None:
        self.items = items

    def fetch_collection_releases(self) -> list[dict[str, Any]]:
        return self.items


class FakeReleasesRepository:
    def __init__(self, releases: list[FakeRelease] | None = None) -> None:
        self.releases = {release.discogs_release_id: release for release in releases or []}

    def save_or_update(self, _db: object, data: InternalReleaseData) -> tuple[FakeRelease, bool]:
        release = self.releases.get(data.discogs_release_id)
        created = release is None
        if release is None:
            release = FakeRelease(
                discogs_release_id=data.discogs_release_id,
                artist=data.artist,
                title=data.title,
                year=data.year,
                format=data.format,
                label=data.label,
                catalog_number=data.catalog_number,
                barcode=data.barcode,
                genres=data.genres,
                styles=data.styles,
                thumbnail_url=data.thumbnail_url,
                cover_image_url=data.cover_image_url,
            )
            self.releases[data.discogs_release_id] = release
        else:
            release.artist = data.artist
            release.title = data.title
            release.year = data.year
            release.format = data.format
            release.label = data.label
            release.catalog_number = data.catalog_number
            release.barcode = data.barcode
            release.genres = data.genres
            release.styles = data.styles
            release.thumbnail_url = data.thumbnail_url
            release.cover_image_url = data.cover_image_url

        return release, created

    def mark_in_collection(
        self,
        _db: object,
        release: FakeRelease,
        *,
        discogs_instance_id: int | None,
        collection_added_at: datetime | None,
        synced_at: datetime,
    ) -> FakeRelease:
        release.in_collection = True
        release.discogs_instance_id = discogs_instance_id
        release.collection_added_at = collection_added_at
        release.collection_removed_at = None
        release.last_discogs_sync_at = synced_at
        return release

    def mark_missing_collection_releases_removed(
        self,
        _db: object,
        active_discogs_release_ids: set[int],
        *,
        removed_at: datetime,
    ) -> int:
        removed_count = 0
        for release_id, release in self.releases.items():
            if release.in_collection and release_id not in active_discogs_release_ids:
                release.in_collection = False
                release.collection_removed_at = removed_at
                release.last_discogs_sync_at = removed_at
                removed_count += 1
        return removed_count


def test_collapse_collection_items_picks_newest_duplicate_copy() -> None:
    items = [
        _collection_item(116, 20, "2020-01-01T10:00:00-07:00", title="Older Copy"),
        _collection_item(116, 10, "2021-01-01T10:00:00-07:00", title="Newer Copy"),
    ]

    [collapsed] = collapse_collection_items(items)

    assert collapsed.discogs_release_id == 116
    assert collapsed.instance_id == 10
    assert collapsed.basic_information["title"] == "Newer Copy"


def test_collapse_collection_items_uses_lowest_instance_id_as_tie_breaker() -> None:
    items = [
        _collection_item(116, 20, "2021-01-01T10:00:00-07:00", title="Higher Instance"),
        _collection_item(116, 10, "2021-01-01T10:00:00-07:00", title="Lower Instance"),
    ]

    [collapsed] = collapse_collection_items(items)

    assert collapsed.instance_id == 10
    assert collapsed.basic_information["title"] == "Lower Instance"


def test_sync_collection_adds_unique_releases_and_marks_them_active() -> None:
    now = datetime(2026, 6, 4, 12, 0, tzinfo=UTC)
    repository = FakeReleasesRepository()
    service = CollectionSyncService(
        discogs_service=FakeDiscogsService(
            [
                _collection_item(116, 20, "2020-01-01T10:00:00-07:00", title="Older Copy"),
                _collection_item(116, 10, "2021-01-01T10:00:00-07:00", title="Newer Copy"),
                _collection_item(202, 30, "2022-01-01T10:00:00-07:00", title="Second Release"),
            ]
        ),
        repository=repository,
        now_provider=lambda: now,
    )

    result = service.sync_collection(db=None)

    assert result.total_items == 3
    assert result.unique_releases == 2
    assert result.added_count == 2
    assert result.updated_count == 0
    assert result.removed_count == 0
    assert repository.releases[116].title == "Newer Copy"
    assert repository.releases[116].in_collection is True
    assert repository.releases[116].discogs_instance_id == 10
    assert repository.releases[116].collection_removed_at is None


def test_sync_collection_marks_missing_active_releases_removed_without_deleting() -> None:
    now = datetime(2026, 6, 4, 12, 0, tzinfo=UTC)
    existing_release = FakeRelease(
        discogs_release_id=999,
        artist="Sold Artist",
        title="Sold Record",
        year=1999,
        format=None,
        label=None,
        catalog_number=None,
        barcode=None,
        genres=None,
        styles=None,
        thumbnail_url=None,
        cover_image_url=None,
        in_collection=True,
    )
    repository = FakeReleasesRepository([existing_release])
    service = CollectionSyncService(
        discogs_service=FakeDiscogsService([_collection_item(116, 10, "2021-01-01T10:00:00-07:00")]),
        repository=repository,
        now_provider=lambda: now,
    )

    result = service.sync_collection(db=None)

    assert result.added_count == 1
    assert result.removed_count == 1
    assert 999 in repository.releases
    assert repository.releases[999].in_collection is False
    assert repository.releases[999].collection_removed_at == now


def test_collapse_collection_items_rejects_missing_basic_information() -> None:
    with pytest.raises(CollectionSyncError, match="basic_information"):
        collapse_collection_items([{"id": 1}])


def _collection_item(
    release_id: int,
    instance_id: int,
    date_added: str,
    *,
    title: str = "Ruff Out Deh",
    artist: str = "Babe Roots",
) -> dict[str, Any]:
    return {
        "id": release_id,
        "instance_id": instance_id,
        "date_added": date_added,
        "basic_information": {
            "id": release_id,
            "title": title,
            "year": 2018,
            "labels": [{"name": "4Weed Records", "catno": "4WDV009"}],
            "artists": [{"name": artist}],
            "genres": ["Electronic", "Reggae"],
            "styles": ["Dub", "Dub Techno"],
            "cover_image": "https://example.test/cover.jpg",
        },
    }
