from sqlalchemy import create_engine
from sqlalchemy.engine import Connection
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


def test_get_sessions_for_month_returns_paged_joined_rows() -> None:
    engine = create_engine("sqlite:///:memory:")
    session_factory = sessionmaker(bind=engine)

    with engine.begin() as connection:
        _create_drilldown_tables(connection)
        _insert_drilldown_releases(connection)
        connection.exec_driver_sql(
            """
            INSERT INTO sessions (id, release_id, rating, mood, played_at, vinyl_side, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                ("session-1", "release-1", 5, "Focused", "2026-05-02T10:00:00+00:00", "A", "2026-05-02T10:00:00+00:00"),
                (
                    "session-2",
                    "release-2",
                    4,
                    "LateNight",
                    "2026-05-12T10:00:00+00:00",
                    "B",
                    "2026-05-12T10:00:00+00:00",
                ),
                ("session-3", "release-3", 5, "Focused", "2026-04-30T10:00:00+00:00", "A", "2026-04-30T10:00:00+00:00"),
            ],
        )

    with session_factory() as db:
        rows = AnalyticsRepository.get_sessions_for_month(db, month="2026-05", limit=1, offset=0)
        total = AnalyticsRepository.count_sessions_for_month(db, month="2026-05")

    assert total == 2
    assert [(session.id, release.title) for session, release in rows] == [("session-2", "Silentintroduction")]


def test_get_records_for_rating_groups_release_counts() -> None:
    engine = create_engine("sqlite:///:memory:")
    session_factory = sessionmaker(bind=engine)

    with engine.begin() as connection:
        _create_drilldown_tables(connection)
        _insert_drilldown_releases(connection)
        connection.exec_driver_sql("""
            INSERT INTO sessions (id, release_id, rating, played_at, created_at)
            VALUES
                ('session-1', 'release-1', 5, '2026-05-02T10:00:00+00:00', '2026-05-02T10:00:00+00:00'),
                ('session-2', 'release-1', 5, '2026-05-03T10:00:00+00:00', '2026-05-03T10:00:00+00:00'),
                ('session-3', 'release-2', 5, '2026-05-04T10:00:00+00:00', '2026-05-04T10:00:00+00:00'),
                ('session-4', 'release-3', 4, '2026-05-05T10:00:00+00:00', '2026-05-05T10:00:00+00:00')
            """)

    with session_factory() as db:
        rows = AnalyticsRepository.get_records_for_rating(db, rating=5, limit=10, offset=0)
        total = AnalyticsRepository.count_records_for_rating(db, rating=5)

    assert total == 2
    assert [(release.title, count) for release, count in rows] == [("Carrier", 2), ("Silentintroduction", 1)]


def test_get_records_for_mood_matches_trimmed_case_insensitive_values() -> None:
    engine = create_engine("sqlite:///:memory:")
    session_factory = sessionmaker(bind=engine)

    with engine.begin() as connection:
        _create_drilldown_tables(connection)
        _insert_drilldown_releases(connection)
        connection.exec_driver_sql("""
            INSERT INTO sessions (id, release_id, mood, played_at, created_at)
            VALUES
                ('session-1', 'release-1', ' Focused ', '2026-05-02T10:00:00+00:00', '2026-05-02T10:00:00+00:00'),
                ('session-2', 'release-1', 'focused', '2026-05-03T10:00:00+00:00', '2026-05-03T10:00:00+00:00'),
                ('session-3', 'release-2', 'Focused', '2026-05-04T10:00:00+00:00', '2026-05-04T10:00:00+00:00'),
                ('session-4', 'release-3', 'LateNight', '2026-05-05T10:00:00+00:00', '2026-05-05T10:00:00+00:00')
            """)

    with session_factory() as db:
        rows = AnalyticsRepository.get_records_for_mood(db, mood="focused", limit=10, offset=0)
        total = AnalyticsRepository.count_records_for_mood(db, mood="focused")

    assert total == 2
    assert [(release.title, count) for release, count in rows] == [("Carrier", 2), ("Silentintroduction", 1)]


def test_get_records_for_style_matches_serialized_styles_case_insensitively() -> None:
    engine = create_engine("sqlite:///:memory:")
    session_factory = sessionmaker(bind=engine)

    with engine.begin() as connection:
        _create_drilldown_tables(connection)
        _insert_drilldown_releases(connection)
        connection.exec_driver_sql("""
            INSERT INTO sessions (id, release_id, played_at, created_at)
            VALUES
                ('session-1', 'release-1', '2026-05-02T10:00:00+00:00', '2026-05-02T10:00:00+00:00'),
                ('session-2', 'release-1', '2026-05-03T10:00:00+00:00', '2026-05-03T10:00:00+00:00'),
                ('session-3', 'release-2', '2026-05-04T10:00:00+00:00', '2026-05-04T10:00:00+00:00'),
                ('session-4', 'release-3', '2026-05-05T10:00:00+00:00', '2026-05-05T10:00:00+00:00')
            """)

    with session_factory() as db:
        rows = AnalyticsRepository.get_records_for_style(db, style="dub techno", limit=10, offset=0)
        total = AnalyticsRepository.count_records_for_style(db, style="dub techno")

    assert total == 2
    assert [(release.title, count) for release, count in rows] == [("Carrier", 2), ("Phylyps Trak", 1)]


def test_drilldown_queries_return_empty_results_for_missing_filters() -> None:
    engine = create_engine("sqlite:///:memory:")
    session_factory = sessionmaker(bind=engine)

    with engine.begin() as connection:
        _create_drilldown_tables(connection)
        _insert_drilldown_releases(connection)
        connection.exec_driver_sql("""
            INSERT INTO sessions (id, release_id, rating, mood, played_at, created_at)
            VALUES
                ('session-1', 'release-1', 5, 'Focused', '2026-05-02T10:00:00+00:00', '2026-05-02T10:00:00+00:00')
            """)

    with session_factory() as db:
        month_rows = AnalyticsRepository.get_sessions_for_month(db, month="2026-06", limit=10, offset=0)
        rating_rows = AnalyticsRepository.get_records_for_rating(db, rating=1, limit=10, offset=0)
        mood_rows = AnalyticsRepository.get_records_for_mood(db, mood="Calm", limit=10, offset=0)
        style_rows = AnalyticsRepository.get_records_for_style(db, style="House", limit=10, offset=0)

        assert AnalyticsRepository.count_sessions_for_month(db, month="2026-06") == 0
        assert AnalyticsRepository.count_records_for_rating(db, rating=1) == 0
        assert AnalyticsRepository.count_records_for_mood(db, mood="Calm") == 0
        assert AnalyticsRepository.count_records_for_style(db, style="House") == 0

    assert month_rows == []
    assert rating_rows == []
    assert mood_rows == []
    assert style_rows == []


def _create_drilldown_tables(connection: Connection) -> None:
    connection.exec_driver_sql("""
        CREATE TABLE releases (
            id TEXT PRIMARY KEY,
            discogs_release_id INTEGER NOT NULL,
            artist TEXT NOT NULL,
            title TEXT NOT NULL,
            year INTEGER,
            label TEXT,
            catalog_number TEXT,
            barcode TEXT,
            genres TEXT,
            styles TEXT,
            cover_image_url TEXT,
            created_at TIMESTAMP,
            updated_at TIMESTAMP
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


def _insert_drilldown_releases(connection: Connection) -> None:
    connection.exec_driver_sql("""
        INSERT INTO releases (
            id,
            discogs_release_id,
            artist,
            title,
            styles,
            cover_image_url,
            created_at,
            updated_at
        )
        VALUES
            (
                'release-1',
                101,
                'Rhythm & Sound',
                'Carrier',
                '["Dub Techno", "Minimal"]',
                'https://example.com/carrier.jpg',
                '2026-05-01T10:00:00+00:00',
                '2026-05-01T10:00:00+00:00'
            ),
            (
                'release-2',
                102,
                'Moodymann',
                'Silentintroduction',
                '["House", "Deep House"]',
                'https://example.com/silent.jpg',
                '2026-05-01T10:00:00+00:00',
                '2026-05-01T10:00:00+00:00'
            ),
            (
                'release-3',
                103,
                'Basic Channel',
                'Phylyps Trak',
                '["dub techno"]',
                'https://example.com/phylyps.jpg',
                '2026-05-01T10:00:00+00:00',
                '2026-05-01T10:00:00+00:00'
            )
        """)
