from datetime import UTC, datetime

from app.models.releases import Releases


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
    assert discogs_service.calls == [(555123, True)]


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
