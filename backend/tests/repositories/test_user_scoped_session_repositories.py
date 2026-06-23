from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.repositories.analytics_repository import AnalyticsRepository
from app.repositories.sessions_repository import SessionsRepository


@pytest.fixture()
def db_session() -> Iterator[Session]:
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(text("""
                CREATE TABLE releases (
                    id TEXT PRIMARY KEY,
                    discogs_release_id BIGINT NOT NULL UNIQUE,
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
                    release_id TEXT,
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
                    artists TEXT NOT NULL DEFAULT '[]',
                    labels TEXT NOT NULL DEFAULT '[]',
                    identifiers TEXT NOT NULL DEFAULT '{}',
                    format_details TEXT NOT NULL DEFAULT '{}',
                    tracklist TEXT NOT NULL DEFAULT '[]',
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
        connection.execute(text("""
                INSERT INTO releases (
                    id, discogs_release_id, artist, title, year, styles, in_collection, is_favorite
                )
                VALUES
                    ('release-1', 1001, 'Artist A', 'Shared Record', 2001, '["Dub Techno"]', 1, 0),
                    ('release-2', 1002, 'Artist B', 'Other Record', 2002, '["House"]', 1, 0)
                """))
        connection.execute(text("""
                INSERT INTO manual_releases (
                    id, user_id, artist, title, year, label, catalog_number, format, genres, styles, cover_image_url
                )
                VALUES
                    (
                        'manual-release-1',
                        'user-a',
                        'Manual Artist',
                        'Manual Record',
                        2026,
                        'Manual Label',
                        'MAN-001',
                        'Vinyl',
                        '["Electronic"]',
                        '["Techno"]',
                        '/media/manual-cover.jpg'
                    ),
                    (
                        'manual-release-2',
                        'user-b',
                        'Other Manual Artist',
                        'Other Manual Record',
                        2026,
                        'Other Manual Label',
                        'MAN-002',
                        'Vinyl',
                        '["Electronic"]',
                        '["House"]',
                        NULL
                    )
                """))

    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


def test_sessions_repository_filters_by_user(db_session: Session) -> None:
    repository = SessionsRepository()
    played_at = datetime(2026, 5, 12, 10, 0, tzinfo=UTC)

    user_a_session = repository.create(
        db_session,
        user_id="user-a",
        release_id="release-1",
        session_group_id=None,
        rating=5,
        mood="Focused",
        notes="A note",
        played_at=played_at,
        vinyl_side="A",
    )
    repository.create(
        db_session,
        user_id="user-b",
        release_id="release-1",
        session_group_id=None,
        rating=2,
        mood="Calm",
        notes="B note",
        played_at=played_at,
        vinyl_side="B",
    )

    user_a_sessions = repository.get_by_release_id(
        db_session,
        "release-1",
        user_id="user-a",
        limit=10,
        offset=0,
    )

    assert [session.id for session in user_a_sessions] == [user_a_session.id]
    assert repository.get_by_id(db_session, user_a_session.id, user_id="user-b") is None
    assert repository.count_all(db_session, user_id="user-a") == 1


def test_sessions_repository_filters_manual_release_sessions_by_user(db_session: Session) -> None:
    repository = SessionsRepository()
    played_at = datetime(2026, 5, 12, 10, 0, tzinfo=UTC)

    user_a_session = repository.create(
        db_session,
        user_id="user-a",
        release_id=None,
        manual_release_id="manual-release-1",
        session_group_id=None,
        rating=5,
        mood="Focused",
        notes="A note",
        played_at=played_at,
        vinyl_side=None,
    )
    repository.create(
        db_session,
        user_id="user-b",
        release_id=None,
        manual_release_id="manual-release-1",
        session_group_id=None,
        rating=4,
        mood="Calm",
        notes=None,
        played_at=played_at,
        vinyl_side=None,
    )

    user_a_sessions = repository.get_by_manual_release_id(
        db_session,
        "manual-release-1",
        user_id="user-a",
        limit=10,
        offset=0,
    )

    assert [session.id for session in user_a_sessions] == [user_a_session.id]


def test_analytics_repository_filters_by_user(db_session: Session) -> None:
    sessions_repository = SessionsRepository()
    analytics_repository = AnalyticsRepository()
    played_at = datetime(2026, 5, 12, 10, 0, tzinfo=UTC)

    sessions_repository.create(
        db_session,
        user_id="user-a",
        release_id="release-1",
        session_group_id=None,
        rating=5,
        mood="Focused",
        notes=None,
        played_at=played_at,
        vinyl_side="A",
    )
    sessions_repository.create(
        db_session,
        user_id="user-b",
        release_id="release-2",
        session_group_id=None,
        rating=2,
        mood="Calm",
        notes=None,
        played_at=played_at,
        vinyl_side="A",
    )

    assert analytics_repository.get_monthly_play_counts(db_session, user_id="user-a") == [("2026-05", 1)]
    assert analytics_repository.get_rating_distribution(db_session, user_id="user-a") == [(5, 1)]
    assert analytics_repository.get_mood_distribution(db_session, user_id="user-a") == [("Focused", 1)]


def test_analytics_repository_includes_manual_release_sessions(db_session: Session) -> None:
    sessions_repository = SessionsRepository()
    analytics_repository = AnalyticsRepository()
    played_at = datetime(2026, 5, 12, 10, 0, tzinfo=UTC)
    later_played_at = datetime(2026, 5, 12, 11, 0, tzinfo=UTC)
    latest_played_at = datetime(2026, 5, 12, 12, 0, tzinfo=UTC)

    discogs_session = sessions_repository.create(
        db_session,
        user_id="user-a",
        release_id="release-1",
        session_group_id=None,
        rating=5,
        mood="Focused",
        notes=None,
        played_at=played_at,
        vinyl_side="A",
    )
    manual_session = sessions_repository.create(
        db_session,
        user_id="user-a",
        release_id=None,
        manual_release_id="manual-release-1",
        session_group_id=None,
        rating=5,
        mood="Focused",
        notes=None,
        played_at=later_played_at,
        vinyl_side="A",
    )
    sessions_repository.create(
        db_session,
        user_id="user-a",
        release_id=None,
        manual_release_id="manual-release-1",
        session_group_id=None,
        rating=4,
        mood="Focused",
        notes=None,
        played_at=latest_played_at,
        vinyl_side="B",
    )
    sessions_repository.create(
        db_session,
        user_id="user-b",
        release_id=None,
        manual_release_id="manual-release-2",
        session_group_id=None,
        rating=5,
        mood="Focused",
        notes=None,
        played_at=latest_played_at,
        vinyl_side="A",
    )
    db_session.execute(
        text("""
            INSERT INTO session_tracks (
                id, session_id, track_position, track_artist, track_title, track_duration, track_sequence
            )
            VALUES
                ('track-1', :discogs_session_id, 'A1', NULL, 'Shared Cut', NULL, 1),
                ('track-2', :manual_session_id, 'A1', NULL, 'Manual Cut', NULL, 1)
            """),
        {
            "discogs_session_id": discogs_session.id,
            "manual_session_id": manual_session.id,
        },
    )

    assert analytics_repository.get_monthly_play_counts(db_session, user_id="user-a") == [("2026-05", 3)]
    month_rows = analytics_repository.get_sessions_for_month(
        db_session,
        user_id="user-a",
        month="2026-05",
        limit=10,
        offset=0,
    )
    assert [release.id for _session, release in month_rows] == [
        "manual-release-1",
        "manual-release-1",
        "release-1",
    ]
    assert month_rows[0][1].discogs_release_id == 0
    assert month_rows[0][1].cover_image_url == "/media/manual-cover.jpg"

    top_records = analytics_repository.get_top_records(db_session, user_id="user-a", limit=5)
    manual_top_record = top_records[0]
    assert manual_top_record[0].id == "manual-release-1"
    assert manual_top_record[1] == 2
    assert round(float(manual_top_record[2]), 1) == 4.5
    assert manual_top_record[3] == "Manual Cut"
    assert manual_top_record[4] == "Focused"

    assert analytics_repository.get_records_for_mood(
        db_session,
        user_id="user-a",
        mood="Focused",
        limit=10,
        offset=0,
    )[
        0
    ] == (manual_top_record[0], 2)
    assert analytics_repository.count_records_for_mood(db_session, user_id="user-a", mood="Focused") == 2
    assert (
        analytics_repository.get_records_for_rating(
            db_session,
            user_id="user-a",
            rating=4,
            limit=10,
            offset=0,
        )[
            0
        ][0].id
        == "manual-release-1"
    )
    assert analytics_repository.get_records_for_style(
        db_session,
        user_id="user-a",
        style="Techno",
        limit=10,
        offset=0,
    ) == [(manual_top_record[0], 2)]
    assert analytics_repository.get_style_distribution(db_session, user_id="user-a") == [
        ("Techno", 2),
        ("Dub Techno", 1),
    ]
