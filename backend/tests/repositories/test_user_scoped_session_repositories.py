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
                    release_id TEXT NOT NULL,
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
        connection.execute(text("""
                INSERT INTO releases (
                    id, discogs_release_id, artist, title, year, styles, in_collection, is_favorite
                )
                VALUES
                    ('release-1', 1001, 'Artist A', 'Shared Record', 2001, '["Dub Techno"]', 1, 0),
                    ('release-2', 1002, 'Artist B', 'Other Record', 2002, '["House"]', 1, 0)
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
