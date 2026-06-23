from sqlalchemy import create_engine
from sqlalchemy.engine import Connection
from sqlalchemy.orm import sessionmaker

from app.repositories.analytics_repository import AnalyticsRepository


def _create_manual_releases_table(connection: Connection) -> None:
    connection.exec_driver_sql("""
        CREATE TABLE manual_releases (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            artist TEXT NOT NULL,
            title TEXT NOT NULL,
            label TEXT NOT NULL,
            catalog_number TEXT,
            barcode TEXT,
            year INTEGER,
            format TEXT NOT NULL,
            genres TEXT,
            styles TEXT,
            artists TEXT,
            labels TEXT,
            identifiers TEXT,
            format_details TEXT,
            tracklist TEXT,
            cover_storage_key TEXT,
            cover_image_url TEXT,
            cover_thumbnail_url TEXT,
            cover_content_type TEXT,
            cover_size_bytes INTEGER,
            in_collection BOOLEAN,
            collection_added_at TIMESTAMP,
            collection_removed_at TIMESTAMP,
            is_favorite BOOLEAN,
            created_at TIMESTAMP,
            updated_at TIMESTAMP
        )
        """)


def test_get_monthly_play_counts_uses_sqlite_month_expression() -> None:
    engine = create_engine("sqlite:///:memory:")
    session_factory = sessionmaker(bind=engine)

    with engine.begin() as connection:
        connection.exec_driver_sql("""
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
                release_id TEXT,
                manual_release_id TEXT,
                user_id TEXT,
                session_group_id TEXT,
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
                genres TEXT,
                styles TEXT
            )
            """)
        connection.exec_driver_sql("""
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
                created_at TIMESTAMP
            )
            """)
        _create_manual_releases_table(connection)
        connection.exec_driver_sql("""
            INSERT INTO releases (id, discogs_release_id, artist, title, genres, styles)
            VALUES
                ('release-1', 101, 'Rhythm & Sound', 'Carrier', NULL, '["Dub Techno", "Minimal"]'),
                ('release-2', 102, 'Moodymann', 'Silentintroduction', NULL, '["House", "Deep House"]'),
                ('release-3', 103, 'Basic Channel', 'Phylyps Trak', NULL, '["dub techno"]')
            """)
        connection.exec_driver_sql("""
            INSERT INTO manual_releases (id, user_id, artist, title, label, format, genres, styles)
            VALUES ('manual-release-1', 'user-1', 'Manual Artist', 'Genre Only', 'Manual Label', 'Vinyl',
                    '["Electronic"]', NULL)
            """)
        connection.exec_driver_sql("""
            INSERT INTO sessions (id, release_id, manual_release_id, user_id, created_at)
            VALUES
                ('session-1', 'release-1', NULL, NULL, '2026-01-02T10:00:00+00:00'),
                ('session-2', 'release-1', NULL, NULL, '2026-01-03T10:00:00+00:00'),
                ('session-3', 'release-2', NULL, NULL, '2026-01-04T10:00:00+00:00'),
                ('session-4', 'release-3', NULL, NULL, '2026-01-05T10:00:00+00:00'),
                ('session-5', NULL, 'manual-release-1', 'user-1', '2026-01-06T10:00:00+00:00')
            """)

    with session_factory() as db:
        rows = AnalyticsRepository.get_style_distribution(db)

    assert rows == [("Dub Techno", 3), ("Minimal", 2), ("Deep House", 1), ("Electronic", 1), ("House", 1)]


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


def test_get_top_records_ranks_by_plays_then_rating_and_includes_track_mood() -> None:
    engine = create_engine("sqlite:///:memory:")
    session_factory = sessionmaker(bind=engine)

    with engine.begin() as connection:
        _create_drilldown_tables(connection)
        _insert_drilldown_releases(connection)
        connection.exec_driver_sql("""
            INSERT INTO sessions (id, release_id, rating, mood, played_at, created_at)
            VALUES
                ('session-1', 'release-1', 5, 'Focused', '2026-05-02T10:00:00+00:00', '2026-05-02T10:00:00+00:00'),
                ('session-2', 'release-1', 3, 'Calm', '2026-05-03T10:00:00+00:00', '2026-05-03T10:00:00+00:00'),
                ('session-3', 'release-2', 5, 'LateNight', '2026-05-04T10:00:00+00:00', '2026-05-04T10:00:00+00:00'),
                ('session-4', 'release-2', 5, 'LateNight', '2026-05-05T10:00:00+00:00', '2026-05-05T10:00:00+00:00'),
                ('session-5', 'release-3', 3, 'Calm', '2026-05-06T10:00:00+00:00', '2026-05-06T10:00:00+00:00'),
                ('session-6', 'release-3', 3, 'Calm', '2026-05-07T10:00:00+00:00', '2026-05-07T10:00:00+00:00'),
                ('session-7', 'release-3', 3, 'Focused', '2026-05-08T10:00:00+00:00', '2026-05-08T10:00:00+00:00')
            """)
        connection.exec_driver_sql("""
            INSERT INTO session_tracks (
                id,
                session_id,
                track_position,
                track_title,
                track_duration,
                track_sequence,
                created_at
            )
            VALUES
                ('track-1', 'session-1', 'A1', 'Carrier', NULL, 1, '2026-05-02T10:00:00+00:00'),
                ('track-2', 'session-2', 'A2', 'Mango Drive', NULL, 2, '2026-05-03T10:00:00+00:00'),
                ('track-3', 'session-3', 'A1', 'Silentintroduction', NULL, 1, '2026-05-04T10:00:00+00:00'),
                ('track-4', 'session-4', 'A1', 'Silentintroduction', NULL, 1, '2026-05-05T10:00:00+00:00'),
                ('track-5', 'session-5', 'A1', 'Phylyps Trak', NULL, 1, '2026-05-06T10:00:00+00:00'),
                ('track-6', 'session-6', 'A1', 'Phylyps Trak', NULL, 1, '2026-05-07T10:00:00+00:00')
            """)

    with session_factory() as db:
        rows = AnalyticsRepository.get_top_records(db, limit=3)

    assert [
        (release.title, plays, round(average_rating, 1), top_track, top_mood)
        for release, plays, average_rating, top_track, top_mood in rows
    ] == [
        ("Phylyps Trak", 3, 3.0, "Phylyps Trak", "Calm"),
        ("Silentintroduction", 2, 5.0, "Silentintroduction", "LateNight"),
        ("Carrier", 2, 4.0, "Carrier", "Calm"),
    ]


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
            INSERT INTO manual_releases (id, user_id, artist, title, label, format, genres, styles)
            VALUES ('manual-release-1', 'user-1', 'Manual Artist', 'Genre Only', 'Manual Label', 'Vinyl',
                    '["Electronic"]', NULL)
            """)
        connection.exec_driver_sql("""
            INSERT INTO sessions (id, release_id, manual_release_id, user_id, played_at, created_at)
            VALUES
                ('session-1', 'release-1', NULL, NULL, '2026-05-02T10:00:00+00:00', '2026-05-02T10:00:00+00:00'),
                ('session-2', 'release-1', NULL, NULL, '2026-05-03T10:00:00+00:00', '2026-05-03T10:00:00+00:00'),
                ('session-3', 'release-2', NULL, NULL, '2026-05-04T10:00:00+00:00', '2026-05-04T10:00:00+00:00'),
                ('session-4', 'release-3', NULL, NULL, '2026-05-05T10:00:00+00:00', '2026-05-05T10:00:00+00:00'),
                ('session-5', NULL, 'manual-release-1', 'user-1', '2026-05-06T10:00:00+00:00',
                 '2026-05-06T10:00:00+00:00')
            """)

    with session_factory() as db:
        rows = AnalyticsRepository.get_records_for_style(db, style="dub techno", limit=10, offset=0)
        total = AnalyticsRepository.count_records_for_style(db, style="dub techno")
        genre_rows = AnalyticsRepository.get_records_for_style(db, style="electronic", limit=10, offset=0)
        genre_total = AnalyticsRepository.count_records_for_style(db, style="electronic")

    assert total == 2
    assert [(release.title, count) for release, count in rows] == [("Carrier", 2), ("Phylyps Trak", 1)]
    assert genre_total == 1
    assert [(release.title, release.styles, count) for release, count in genre_rows] == [
        ("Genre Only", ["Electronic"], 1)
    ]


def test_get_records_for_style_page_returns_slice_and_total_from_one_result_set() -> None:
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
        rows, total = AnalyticsRepository.get_records_for_style_page(db, style="dub techno", limit=1, offset=1)

    assert total == 2
    assert [(release.title, count) for release, count in rows] == [("Phylyps Trak", 1)]


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
            format TEXT,
            label TEXT,
            catalog_number TEXT,
            barcode TEXT,
            genres TEXT,
            styles TEXT,
            thumbnail_url TEXT,
            cover_image_url TEXT,
            in_collection BOOLEAN,
            collection_added_at TIMESTAMP,
            collection_removed_at TIMESTAMP,
            last_discogs_sync_at TIMESTAMP,
            discogs_instance_id INTEGER,
            is_favorite BOOLEAN,
            created_at TIMESTAMP,
            updated_at TIMESTAMP
        )
        """)
    _create_manual_releases_table(connection)
    connection.exec_driver_sql("""
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
            created_at TIMESTAMP
        )
        """)
    connection.exec_driver_sql("""
        CREATE TABLE session_tracks (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            track_position TEXT NOT NULL,
            track_title TEXT NOT NULL,
            track_duration TEXT,
            track_sequence INTEGER,
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
            format,
            styles,
            thumbnail_url,
            cover_image_url,
            in_collection,
            created_at,
            updated_at
        )
        VALUES
            (
                'release-1',
                101,
                'Rhythm & Sound',
                'Carrier',
                'Vinyl',
                '["Dub Techno", "Minimal"]',
                'https://example.com/carrier-thumb.jpg',
                'https://example.com/carrier.jpg',
                1,
                '2026-05-01T10:00:00+00:00',
                '2026-05-01T10:00:00+00:00'
            ),
            (
                'release-2',
                102,
                'Moodymann',
                'Silentintroduction',
                'Vinyl',
                '["House", "Deep House"]',
                'https://example.com/silent-thumb.jpg',
                'https://example.com/silent.jpg',
                1,
                '2026-05-01T10:00:00+00:00',
                '2026-05-01T10:00:00+00:00'
            ),
            (
                'release-3',
                103,
                'Basic Channel',
                'Phylyps Trak',
                'Vinyl',
                '["dub techno"]',
                'https://example.com/phylyps-thumb.jpg',
                'https://example.com/phylyps.jpg',
                1,
                '2026-05-01T10:00:00+00:00',
                '2026-05-01T10:00:00+00:00'
            )
        """)
