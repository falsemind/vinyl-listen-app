from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.repositories.analytics_repository import AnalyticsRepository


def test_get_monthly_play_counts_uses_sqlite_month_expression() -> None:
    engine = create_engine("sqlite:///:memory:")
    session_factory = sessionmaker(bind=engine)

    with engine.begin() as connection:
        connection.exec_driver_sql("""
            CREATE TABLE sessions (
                id TEXT PRIMARY KEY,
                release_id TEXT NOT NULL,
                rating INTEGER,
                mood TEXT,
                notes TEXT,
                played_at TIMESTAMP,
                vinyl_side TEXT,
                created_at TIMESTAMP
            )
            """)
        connection.exec_driver_sql("""
            INSERT INTO sessions (id, release_id, played_at)
            VALUES
                ('session-1', 'release-1', '2026-01-02T10:00:00+00:00'),
                ('session-2', 'release-1', '2026-01-18T10:00:00+00:00'),
                ('session-3', 'release-2', '2026-02-03T10:00:00+00:00')
            """)

    with session_factory() as db:
        rows = AnalyticsRepository.get_monthly_play_counts(db)

    assert [(month, plays) for month, plays in rows] == [("2026-01", 2), ("2026-02", 1)]


def test_get_mood_distribution_combines_case_variants() -> None:
    engine = create_engine("sqlite:///:memory:")
    session_factory = sessionmaker(bind=engine)

    with engine.begin() as connection:
        connection.exec_driver_sql("""
            CREATE TABLE sessions (
                id TEXT PRIMARY KEY,
                release_id TEXT NOT NULL,
                rating INTEGER,
                mood TEXT,
                notes TEXT,
                played_at TIMESTAMP,
                vinyl_side TEXT,
                created_at TIMESTAMP
            )
            """)
        connection.exec_driver_sql("""
            INSERT INTO sessions (id, release_id, mood, created_at)
            VALUES
                ('session-1', 'release-1', 'LateNight', '2026-01-02T10:00:00+00:00'),
                ('session-2', 'release-1', 'latenight', '2026-01-03T10:00:00+00:00'),
                ('session-3', 'release-2', 'Focused', '2026-01-04T10:00:00+00:00')
            """)

    with session_factory() as db:
        rows = AnalyticsRepository.get_mood_distribution(db)

    assert rows == [("LateNight", 2), ("Focused", 1)]


def test_get_style_distribution_counts_release_styles_per_session() -> None:
    engine = create_engine("sqlite:///:memory:")
    session_factory = sessionmaker(bind=engine)

    with engine.begin() as connection:
        connection.exec_driver_sql("""
            CREATE TABLE releases (
                id TEXT PRIMARY KEY,
                discogs_release_id INTEGER NOT NULL,
                artist TEXT NOT NULL,
                title TEXT NOT NULL,
                styles TEXT
            )
            """)
        connection.exec_driver_sql("""
            CREATE TABLE sessions (
                id TEXT PRIMARY KEY,
                release_id TEXT NOT NULL,
                rating INTEGER,
                mood TEXT,
                notes TEXT,
                played_at TIMESTAMP,
                vinyl_side TEXT,
                created_at TIMESTAMP
            )
            """)
        connection.exec_driver_sql("""
            INSERT INTO releases (id, discogs_release_id, artist, title, styles)
            VALUES
                ('release-1', 101, 'Rhythm & Sound', 'Carrier', '["Dub Techno", "Minimal"]'),
                ('release-2', 102, 'Moodymann', 'Silentintroduction', '["House", "Deep House"]'),
                ('release-3', 103, 'Basic Channel', 'Phylyps Trak', '["dub techno"]')
            """)
        connection.exec_driver_sql("""
            INSERT INTO sessions (id, release_id, created_at)
            VALUES
                ('session-1', 'release-1', '2026-01-02T10:00:00+00:00'),
                ('session-2', 'release-1', '2026-01-03T10:00:00+00:00'),
                ('session-3', 'release-2', '2026-01-04T10:00:00+00:00'),
                ('session-4', 'release-3', '2026-01-05T10:00:00+00:00')
            """)

    with session_factory() as db:
        rows = AnalyticsRepository.get_style_distribution(db)

    assert rows == [("Dub Techno", 3), ("Minimal", 2), ("Deep House", 1), ("House", 1)]
