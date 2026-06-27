from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.repositories.analytics_repository import AnalyticsRepository
from app.repositories.manual_release_repository import ManualReleaseRepository
from app.schemas.manual_releases import ManualReleaseFormat, ManualReleaseFormData


class _FakeDialect:
    def __init__(self, name: str) -> None:
        self.name = name


class _FakeBind:
    def __init__(self, dialect_name: str) -> None:
        self.dialect = _FakeDialect(dialect_name)


class _FakeLockSession:
    def __init__(self, dialect_name: str) -> None:
        self.bind = _FakeBind(dialect_name)
        self.executed: list[tuple[str, dict]] = []

    def get_bind(self) -> _FakeBind:
        return self.bind

    def execute(self, statement, parameters: dict) -> None:
        self.executed.append((str(statement), parameters))


@pytest.fixture()
def db_session() -> Iterator[Session]:
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        _create_manual_release_tables(connection)
        _create_shared_release_history_tables(connection)

    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


def test_lock_draft_capacity_for_user_uses_postgres_transaction_advisory_lock() -> None:
    db_session = _FakeLockSession("postgresql")
    repository = ManualReleaseRepository()

    repository.lock_draft_capacity_for_user(db_session, user_id="user-a")

    assert len(db_session.executed) == 1
    statement, parameters = db_session.executed[0]
    assert "pg_advisory_xact_lock" in statement
    assert "hashtext" in statement
    assert parameters["user_id"] == "user-a"


def test_lock_draft_capacity_for_user_is_noop_for_non_postgres_dialects() -> None:
    db_session = _FakeLockSession("sqlite")
    repository = ManualReleaseRepository()

    repository.lock_draft_capacity_for_user(db_session, user_id="user-a")

    assert db_session.executed == []


def test_update_draft_cover_persists_cover_metadata(db_session: Session) -> None:
    repository = ManualReleaseRepository()
    draft = repository.create_draft(
        db_session,
        user_id="user-a",
        form_data=ManualReleaseFormData(title="Partial"),
    )

    updated = repository.update_draft_cover(
        db_session,
        draft,
        cover_storage_key="manual-release-covers/user-a/draft-1/cover.png",
        cover_image_url="/media/manual-release-covers/user-a/draft-1/cover.png",
        cover_thumbnail_url="/media/manual-release-covers/user-a/draft-1/cover.png",
        cover_content_type="image/png",
        cover_size_bytes=1024,
    )

    db_session.refresh(updated)
    assert updated.cover_storage_key == "manual-release-covers/user-a/draft-1/cover.png"
    assert updated.cover_image_url == "/media/manual-release-covers/user-a/draft-1/cover.png"
    assert updated.cover_thumbnail_url == "/media/manual-release-covers/user-a/draft-1/cover.png"
    assert updated.cover_content_type == "image/png"
    assert updated.cover_size_bytes == 1024


def test_manual_release_save_preserves_collection_and_history_boundaries(
    db_session: Session,
) -> None:
    repository = ManualReleaseRepository()
    form_data = ManualReleaseFormData(
        artists=["Manual Artist"],
        title="Private Press",
        year=1998,
        label="Living Room Records",
        catalog_number="LR-001",
        barcode="1234 5678",
        format=ManualReleaseFormat.VINYL,
    )

    draft = repository.create_draft(
        db_session,
        user_id="user-a",
        form_data=form_data,
    )

    manual_release = repository.create_manual_release(
        db_session,
        user_id="user-a",
        form_data=form_data,
        draft=draft,
    )

    assert manual_release.user_id == "user-a"
    assert manual_release.in_collection is True
    assert manual_release.collection_added_at is not None
    assert manual_release.collection_removed_at is None
    assert manual_release.artist == "Manual Artist"
    assert manual_release.year == 1998
    assert manual_release.barcode == "12345678"
    assert manual_release.identifiers["year"] == 1998
    assert repository.search_collection_releases(
        db_session,
        user_id="user-a",
        year=1998,
        artist=None,
        title=None,
        catalog=None,
        barcode=None,
        limit=10,
        offset=0,
    ) == [manual_release]
    assert (
        repository.search_collection_releases(
            db_session,
            user_id="user-a",
            year=1999,
            artist=None,
            title=None,
            catalog=None,
            barcode=None,
            limit=10,
            offset=0,
        )
        == []
    )

    assert _count_rows(db_session, "manual_releases") == 1
    assert _count_rows(db_session, "manual_release_drafts") == 0
    assert _count_rows(db_session, "releases") == 0
    assert _count_rows(db_session, "sessions") == 0
    assert _count_rows(db_session, "session_tracks") == 0

    analytics_repository = AnalyticsRepository()
    assert analytics_repository.get_monthly_play_counts(db_session, user_id="user-a") == []
    assert analytics_repository.get_top_records(db_session, limit=10, user_id="user-a") == []
    assert analytics_repository.get_rating_distribution(db_session, user_id="user-a") == []
    assert analytics_repository.get_mood_distribution(db_session, user_id="user-a") == []


def test_update_manual_release_persists_form_data_without_changing_identity(db_session: Session) -> None:
    repository = ManualReleaseRepository()
    release = repository.create_manual_release(
        db_session,
        user_id="user-a",
        form_data=ManualReleaseFormData(
            artists=["Manual Artist"],
            title="Original Title",
            year=1998,
            label="Original Label",
            catalog_number="ORIG-1",
            barcode="1234 5678",
            format=ManualReleaseFormat.VINYL,
        ),
    )
    original_id = release.id
    original_collection_added_at = release.collection_added_at

    updated = repository.update_manual_release(
        db_session,
        release,
        form_data=ManualReleaseFormData(
            artists=["Updated Artist", "Second Artist"],
            title="Updated Title",
            year=2001,
            label="Updated Label",
            catalog_number="UPD-2",
            barcode="9 8765 4321",
            format="CD",
            tracklist=[{"title": "Updated Track", "duration": "3:05"}],
        ),
    )

    db_session.expire_all()
    persisted = repository.get_release(db_session, original_id, user_id="user-a")
    assert persisted is not None
    assert updated.id == original_id
    assert persisted.id == original_id
    assert persisted.user_id == "user-a"
    assert persisted.in_collection is True
    assert persisted.collection_added_at == original_collection_added_at
    assert persisted.artist == "Updated Artist, Second Artist"
    assert persisted.title == "Updated Title"
    assert persisted.year == 2001
    assert persisted.label == "Updated Label"
    assert persisted.catalog_number == "UPD-2"
    assert persisted.barcode == "987654321"
    assert persisted.format == "CD"
    assert persisted.artists == [{"name": "Updated Artist"}, {"name": "Second Artist"}]
    assert persisted.labels == [{"name": "Updated Label", "catalog_number": "UPD-2"}]
    assert persisted.identifiers == {
        "catalog_number": "UPD-2",
        "barcode": "987654321",
        "year": 2001,
    }
    assert persisted.format_details == {
        "format": "CD",
        "vinyl_size": None,
        "vinyl_speed": None,
        "vinyl_disc_count": None,
    }
    assert persisted.tracklist == [{"title": "Updated Track", "position": None, "duration": "3:05", "credits": []}]


def test_saved_manual_release_cover_updates_and_clears_persist(db_session: Session) -> None:
    repository = ManualReleaseRepository()
    release = repository.create_manual_release(
        db_session,
        user_id="user-a",
        form_data=ManualReleaseFormData(
            artists=["Manual Artist"],
            title="Private Press",
            label="Living Room Records",
            format="CD",
        ),
    )

    repository.update_manual_release_cover(
        db_session,
        release,
        cover_storage_key="manual-release-covers/user-a/manual-1/cover.webp",
        cover_image_url="/media/manual-release-covers/user-a/manual-1/cover.webp",
        cover_thumbnail_url="/media/manual-release-covers/user-a/manual-1/cover.webp",
        cover_content_type="image/webp",
        cover_size_bytes=2048,
    )

    db_session.expire_all()
    persisted = repository.get_release(db_session, release.id, user_id="user-a")
    assert persisted is not None
    assert persisted.cover_storage_key == "manual-release-covers/user-a/manual-1/cover.webp"
    assert persisted.cover_image_url == "/media/manual-release-covers/user-a/manual-1/cover.webp"
    assert persisted.cover_thumbnail_url == "/media/manual-release-covers/user-a/manual-1/cover.webp"
    assert persisted.cover_content_type == "image/webp"
    assert persisted.cover_size_bytes == 2048

    repository.clear_manual_release_cover(db_session, persisted)

    db_session.expire_all()
    cleared = repository.get_release(db_session, release.id, user_id="user-a")
    assert cleared is not None
    assert cleared.cover_storage_key is None
    assert cleared.cover_image_url is None
    assert cleared.cover_thumbnail_url is None
    assert cleared.cover_content_type is None
    assert cleared.cover_size_bytes is None


def _count_rows(db_session: Session, table_name: str) -> int:
    return db_session.execute(text(f"SELECT count(*) FROM {table_name}")).scalar_one()


def _create_manual_release_tables(connection) -> None:
    connection.execute(text("""
        CREATE TABLE manual_releases (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            artist TEXT NOT NULL,
            title TEXT NOT NULL,
            year INTEGER,
            label TEXT NOT NULL,
            catalog_number TEXT,
            barcode TEXT,
            format TEXT NOT NULL,
            genres TEXT,
            styles TEXT,
            artists TEXT NOT NULL,
            labels TEXT NOT NULL,
            identifiers TEXT NOT NULL,
            format_details TEXT NOT NULL,
            tracklist TEXT NOT NULL,
            cover_storage_key TEXT,
            cover_image_url TEXT,
            cover_thumbnail_url TEXT,
            cover_content_type TEXT,
            cover_size_bytes INTEGER,
            in_collection BOOLEAN NOT NULL DEFAULT 1,
            collection_added_at TIMESTAMP,
            collection_removed_at TIMESTAMP,
            is_favorite BOOLEAN NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """))
    connection.execute(text("""
        CREATE TABLE manual_release_drafts (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            form_data TEXT NOT NULL,
            completion_state TEXT,
            cover_storage_key TEXT,
            cover_image_url TEXT,
            cover_thumbnail_url TEXT,
            cover_content_type TEXT,
            cover_size_bytes INTEGER,
            validation_version INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """))


def _create_shared_release_history_tables(connection) -> None:
    connection.execute(text("""
        CREATE TABLE releases (
            id TEXT PRIMARY KEY,
            discogs_release_id BIGINT UNIQUE,
            artist TEXT NOT NULL,
            title TEXT NOT NULL,
            year INTEGER,
            format TEXT,
            label TEXT,
            catalog_number TEXT,
            barcode TEXT,
            genres TEXT,
            styles TEXT,
            thumbnail_url TEXT,
            cover_image_url TEXT,
            in_collection BOOLEAN NOT NULL DEFAULT 0,
            collection_added_at TIMESTAMP,
            collection_removed_at TIMESTAMP,
            last_discogs_sync_at TIMESTAMP,
            discogs_instance_id BIGINT,
            is_favorite BOOLEAN NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """))
    connection.execute(text("""
        CREATE TABLE sessions (
            id TEXT PRIMARY KEY,
            release_id TEXT NOT NULL,
            manual_release_id TEXT,
            user_id TEXT,
            session_group_id TEXT,
            rating INTEGER,
            mood TEXT,
            notes TEXT,
            played_at TIMESTAMP,
            vinyl_side TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """))
    connection.execute(text("""
        CREATE TABLE session_tracks (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            track_position TEXT NOT NULL,
            track_artist TEXT,
            track_title TEXT NOT NULL,
            track_duration TEXT,
            track_sequence INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """))
