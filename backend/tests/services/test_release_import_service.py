from datetime import UTC, datetime

import pytest

from app.models.releases import Releases
from app.services.discogs_service import DiscogsConfigurationError
from app.services.release_import_service import ReleaseImportService


def test_import_release_creates_a_new_internal_release(
    discogs_release_payload,
    release_import_discogs_service_factory,
    release_import_repository_factory,
    build_release_import_service,
) -> None:
    discogs_service = release_import_discogs_service_factory(discogs_release_payload)
    repository = release_import_repository_factory()
    service = build_release_import_service(discogs_service=discogs_service, repository=repository)

    result = service.import_release(db=object(), discogs_release_id=555123)

    assert result.created is True
    assert result.status == "created"
    assert result.release.id == "release-123"
    assert result.release.discogs_release_id == 555123
    assert result.release.cover_image_url == "https://img.discogs.com/thumb.jpg"
    assert discogs_service.calls == [(555123, False)]


def test_import_release_updates_existing_release_when_present(
    discogs_release_payload,
    release_import_discogs_service_factory,
    release_import_repository_factory,
    build_release_import_service,
) -> None:
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
    discogs_service = release_import_discogs_service_factory(discogs_release_payload)
    repository = release_import_repository_factory(existing_release)
    service = build_release_import_service(discogs_service=discogs_service, repository=repository)

    result = service.import_release(db=object(), discogs_release_id=555123, force_refresh=True)

    assert result.created is False
    assert result.status == "updated"
    assert result.release.id == "release-123"
    assert result.release.artist == "Boards of Canada"
    assert result.release.title == "Music Has The Right To Children"
    assert result.release.cover_image_url == "https://img.discogs.com/thumb.jpg"
    assert discogs_service.calls == [(555123, True)]


def test_import_release_to_collection_imports_full_release_and_marks_active(
    discogs_release_payload,
    release_import_discogs_service_factory,
    release_import_repository_factory,
    build_release_import_service,
) -> None:
    discogs_service = release_import_discogs_service_factory(discogs_release_payload)
    repository = release_import_repository_factory()
    service = build_release_import_service(discogs_service=discogs_service, repository=repository)

    result = service.import_release_to_collection(db=object(), discogs_release_id=555123)

    assert result.created is True
    assert result.release.id == "release-123"
    assert result.release.in_collection is True
    assert result.release.collection_added_at is not None
    assert result.release.collection_removed_at is None
    assert result.release.discogs_instance_id is None
    assert result.release.last_discogs_sync_at == result.release.collection_added_at
    assert discogs_service.calls == [(555123, False)]
    assert len(repository.collection_mark_calls) == 1
    release_id, discogs_instance_id, collection_added_at, synced_at = repository.collection_mark_calls[0]
    assert release_id == "release-123"
    assert discogs_instance_id is None
    assert collection_added_at == synced_at


def test_import_release_to_collection_reactivates_existing_release(
    discogs_release_payload,
    release_import_discogs_service_factory,
    release_import_repository_factory,
    build_release_import_service,
) -> None:
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
        in_collection=False,
        collection_removed_at=datetime(2026, 6, 1, tzinfo=UTC),
        created_at=datetime(2026, 4, 18, tzinfo=UTC),
        updated_at=datetime(2026, 4, 18, tzinfo=UTC),
    )
    discogs_service = release_import_discogs_service_factory(discogs_release_payload)
    repository = release_import_repository_factory(existing_release)
    service = build_release_import_service(discogs_service=discogs_service, repository=repository)

    result = service.import_release_to_collection(db=object(), discogs_release_id=555123, force_refresh=True)

    assert result.created is False
    assert result.release is existing_release
    assert result.release.in_collection is True
    assert result.release.collection_removed_at is None
    assert result.release.title == "Music Has The Right To Children"
    assert discogs_service.calls == [(555123, True)]
    assert len(repository.collection_mark_calls) == 1


def test_import_release_requires_backend_discogs_token_when_token_missing() -> None:
    class MissingTokenIntegrationService:
        def __init__(self) -> None:
            self.authenticated_calls = 0

        def build_discogs_service(self, _db):
            self.authenticated_calls += 1
            raise DiscogsConfigurationError("Discogs token is not configured.")

    integration_service = MissingTokenIntegrationService()
    service = ReleaseImportService(
        discogs_integration_service=integration_service,
    )

    with pytest.raises(DiscogsConfigurationError):
        service.import_release(db=object(), discogs_release_id=555123)

    assert integration_service.authenticated_calls == 1


def test_import_client_discogs_release_persists_payload_without_fetching_discogs(
    discogs_release_payload,
    release_import_repository_factory,
    release_import_discogs_repository_factory,
    build_release_import_service,
) -> None:
    repository = release_import_repository_factory()
    discogs_repository = release_import_discogs_repository_factory()
    service = build_release_import_service(repository=repository, discogs_repository=discogs_repository)

    result = service.import_client_discogs_release(db=object(), raw_payload=discogs_release_payload)

    assert result.created is True
    assert result.release.id == "release-123"
    assert result.release.discogs_release_id == 555123
    assert repository.saved_payloads == [(555123, "Music Has The Right To Children")]
    assert discogs_repository.upsert_calls == [(555123, discogs_release_payload)]


def test_get_release_returns_repository_result(
    release_import_repository_factory,
    build_release_import_service,
) -> None:
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
    repository = release_import_repository_factory(release)
    service = build_release_import_service(repository=repository)

    result = service.get_release(db=object(), release_id="release-123")

    assert result is release


def test_refresh_release_fetches_full_release_with_force_refresh(
    discogs_release_payload,
    release_import_discogs_service_factory,
    release_import_repository_factory,
    build_release_import_service,
) -> None:
    release = Releases(
        id="release-123",
        discogs_release_id=555123,
        artist="Old Artist",
        title="Old Title",
        year=1998,
        label="Warp Records",
        catalog_number="WARPLP55",
        barcode=None,
        genres=None,
        styles=None,
        cover_image_url=None,
        created_at=datetime(2026, 4, 18, tzinfo=UTC),
        updated_at=datetime(2026, 4, 18, tzinfo=UTC),
    )
    discogs_service = release_import_discogs_service_factory(discogs_release_payload)
    repository = release_import_repository_factory(release)
    service = build_release_import_service(discogs_service=discogs_service, repository=repository)

    result = service.refresh_release(db=object(), release_id="release-123")

    assert result is not None
    assert result.created is False
    assert result.release.title == "Music Has The Right To Children"
    assert discogs_service.calls == [(555123, True)]


def test_get_available_sides_returns_discogs_track_sides(
    release_import_discogs_repository_factory,
    build_release_import_service,
) -> None:
    discogs_repository = release_import_discogs_repository_factory(
        {
            "tracklist": [
                {"position": "A1"},
                {"position": "A2"},
                {"position": "AA"},
            ]
        }
    )
    service = build_release_import_service(discogs_repository=discogs_repository)

    assert service.get_available_sides(db=object(), discogs_release_id=555123) == ["A", "AA"]


def test_get_available_side_options_distinguishes_repeated_side_names(
    release_import_discogs_repository_factory,
    build_release_import_service,
) -> None:
    discogs_repository = release_import_discogs_repository_factory(
        {
            "tracklist": [
                {"position": "X1"},
                {"position": "X2"},
                {"position": "Y1"},
                {"position": "X1"},
                {"position": "Y1"},
            ]
        }
    )
    service = build_release_import_service(discogs_repository=discogs_repository)

    options = service.get_available_side_options(db=object(), discogs_release_id=555123)

    assert [(option.value, option.label, option.side, option.disc_number) for option in options] == [
        ("1:X", "Disc 1 - Side X", "X", 1),
        ("1:Y", "Disc 1 - Side Y", "Y", 1),
        ("2:X", "Disc 2 - Side X", "X", 2),
        ("2:Y", "Disc 2 - Side Y", "Y", 2),
    ]


def test_get_tracklist_returns_discogs_tracks(
    release_import_discogs_repository_factory,
    build_release_import_service,
) -> None:
    discogs_repository = release_import_discogs_repository_factory(
        {
            "tracklist": [
                {"position": "X1", "type_": "heading", "title": "Side X"},
                {
                    "position": "X2",
                    "type_": "track",
                    "title": "S.O.U.R",
                    "duration": "",
                    "extraartists": [{"name": "Target Artist (2)", "role": "Remix"}],
                },
                {"position": "Y1", "type_": "track", "title": "Another Tune", "duration": "5:12"},
            ]
        }
    )
    service = build_release_import_service(discogs_repository=discogs_repository)

    tracks = service.get_tracklist(db=object(), discogs_release_id=555123)

    assert [(track.position, track.title, track.duration) for track in tracks] == [
        ("X2", "S.O.U.R", None),
        ("Y1", "Another Tune", "5:12"),
    ]
    assert [(artist.name, artist.role) for artist in tracks[0].extra_artists] == [("Target Artist", "Remix")]
    assert tracks[1].extra_artists == []


def test_get_artists_returns_discogs_release_artists(
    release_import_discogs_repository_factory,
    build_release_import_service,
) -> None:
    discogs_repository = release_import_discogs_repository_factory(
        {
            "artists": [
                {"id": 194, "name": "Boards Of Canada"},
                {"id": 355, "name": "Karma (54)"},
                {"name": "No ID"},
            ]
        }
    )
    service = build_release_import_service(discogs_repository=discogs_repository)

    artists = service.get_artists(db=object(), discogs_release_id=555123)

    assert [(artist.name, artist.discogs_artist_id) for artist in artists] == [
        ("Boards Of Canada", 194),
        ("Karma", 355),
    ]
