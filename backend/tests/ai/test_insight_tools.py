from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.ai.insight_tools import AiInsightToolRunner


def test_tool_runner_returns_grounded_collection_context() -> None:
    engine = create_engine("sqlite:///:memory:")
    session_factory = sessionmaker(bind=engine)
    _create_collection_tables(engine)

    with session_factory() as db:
        results = AiInsightToolRunner().run(db, user_id="user-a", message="What style did I play most lately?")

    assert [result.name for result in results] == [
        "get_listening_summary",
        "get_recent_sessions",
        "get_top_records",
        "get_style_distribution",
    ]
    rendered_context = "\n".join(result.content for result in results)
    assert "Total logged listening sessions: 3." in rendered_context
    assert "Rhythm & Sound - Carrier" in rendered_context
    assert "Dub Techno: 2" in rendered_context


def test_tool_runner_selects_mood_and_rating_tools() -> None:
    engine = create_engine("sqlite:///:memory:")
    session_factory = sessionmaker(bind=engine)
    _create_collection_tables(engine)

    with session_factory() as db:
        results = AiInsightToolRunner().run(db, user_id="user-a", message="How are my mood and rating patterns?")

    assert [result.name for result in results] == [
        "get_listening_summary",
        "get_mood_distribution",
        "get_rating_distribution",
    ]
    rendered_context = "\n".join(result.content for result in results)
    assert "Focused: 2" in rendered_context
    assert "5: 2" in rendered_context


def test_tool_runner_prioritizes_session_notes_for_recommendations() -> None:
    engine = create_engine("sqlite:///:memory:")
    session_factory = sessionmaker(bind=engine)
    _create_collection_tables(engine)

    with session_factory() as db:
        results = AiInsightToolRunner().run(
            db, user_id="user-a", message="Recommend something special based on my notes"
        )

    assert [result.name for result in results] == [
        "get_listening_summary",
        "get_session_notes",
        "get_recent_sessions",
        "get_top_records",
    ]
    rendered_context = "\n".join(result.content for result in results)
    assert 'note="Huge low end, felt meditative after a long day."' in rendered_context
    assert 'note="Warm and loose, best for late-night focus."' in rendered_context


def test_tool_runner_uses_spotify_overlap_and_time_patterns() -> None:
    engine = create_engine("sqlite:///:memory:")
    session_factory = sessionmaker(bind=engine)
    _create_collection_tables(engine)
    _create_spotify_rollup_tables(engine)

    with session_factory() as db:
        results = AiInsightToolRunner().run(
            db,
            user_id="user-a",
            message="How does my Spotify streaming overlap with my vinyl collection at night?",
        )

    result_names = [result.name for result in results]
    assert "get_spotify_vinyl_overlap_summary" in result_names
    assert "get_spotify_top_artists_by_period" in result_names
    assert "get_spotify_listening_time_patterns" in result_names
    assert "get_spotify_collection_recommendation_signals" in result_names
    rendered_context = "\n".join(result.content for result in results)
    assert "Artist overlap: Rhythm & Sound" in rendered_context
    assert "Release overlap: Rhythm & Sound - Carrier" in rendered_context
    assert "04:00: plays=2" in rendered_context
    assert "Monthly Spotify signal: 2020-01" in rendered_context


def test_tool_runner_uses_spotify_collection_recommendation_signals() -> None:
    engine = create_engine("sqlite:///:memory:")
    session_factory = sessionmaker(bind=engine)
    _create_collection_tables(engine)
    _create_spotify_rollup_tables(engine)

    with session_factory() as db:
        results = AiInsightToolRunner().run(
            db,
            user_id="user-a",
            message="Recommend from my collection using Spotify history",
        )

    result_names = [result.name for result in results]
    assert "get_spotify_collection_recommendation_signals" in result_names
    rendered_context = "\n".join(result.content for result in results)
    assert "Collection recommendation signal: Rhythm & Sound - Carrier" in rendered_context
    assert "release_id=release-1" in rendered_context


def _create_collection_tables(engine) -> None:
    with engine.begin() as connection:
        connection.exec_driver_sql("""
            CREATE TABLE releases (
                id TEXT PRIMARY KEY,
                discogs_release_id INTEGER NOT NULL,
                artist TEXT NOT NULL,
                title TEXT NOT NULL,
                format TEXT,
                label TEXT,
                year INTEGER,
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
        connection.exec_driver_sql("""
            CREATE TABLE sessions (
                id TEXT PRIMARY KEY,
                user_id TEXT,
                release_id TEXT NOT NULL,
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
                track_artist TEXT,
                track_title TEXT NOT NULL,
                track_duration TEXT,
                track_sequence INTEGER,
                created_at TIMESTAMP
            )
            """)
        connection.exec_driver_sql("""
            INSERT INTO releases (id, discogs_release_id, artist, title, styles, created_at, updated_at)
            VALUES
                ('release-1', 101, 'Rhythm & Sound', 'Carrier',
                 '["Dub Techno", "Minimal"]', '2026-01-01', '2026-01-01'),
                ('release-2', 102, 'Moodymann', 'Silentintroduction',
                 '["House"]', '2026-01-01', '2026-01-01')
            """)
        connection.exec_driver_sql("""
            INSERT INTO sessions (id, user_id, release_id, rating, mood, notes, played_at, vinyl_side, created_at)
            VALUES
                ('session-1', 'user-a', 'release-1', 5, 'Focused',
                 'Huge low end, felt meditative after a long day.',
                 '2026-01-03T10:00:00+00:00', 'A', '2026-01-03T10:00:00+00:00'),
                ('session-2', 'user-a', 'release-1', 4, 'Focused',
                 NULL,
                 '2026-01-02T10:00:00+00:00', 'B', '2026-01-02T10:00:00+00:00'),
                ('session-3', 'user-a', 'release-2', 5, 'Late Night',
                 'Warm and loose, best for late-night focus.',
                 '2026-01-01T10:00:00+00:00', 'A', '2026-01-01T10:00:00+00:00')
            """)


def _create_spotify_rollup_tables(engine) -> None:
    with engine.begin() as connection:
        connection.exec_driver_sql("""
            CREATE TABLE spotify_artist_stats (
                stat_key TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                normalized_artist_name TEXT NOT NULL,
                artist_name TEXT NOT NULL,
                play_count INTEGER NOT NULL,
                meaningful_play_count INTEGER NOT NULL,
                skipped_count INTEGER NOT NULL,
                total_ms_played INTEGER NOT NULL,
                first_played_at TIMESTAMP NOT NULL,
                last_played_at TIMESTAMP NOT NULL
            )
            """)
        connection.exec_driver_sql("""
            CREATE TABLE spotify_hourly_stats (
                stat_key TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                played_hour INTEGER NOT NULL,
                play_count INTEGER NOT NULL,
                meaningful_play_count INTEGER NOT NULL,
                skipped_count INTEGER NOT NULL,
                total_ms_played INTEGER NOT NULL
            )
            """)
        connection.exec_driver_sql("""
            CREATE TABLE spotify_monthly_artist_stats (
                stat_key TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                played_year_month TEXT NOT NULL,
                normalized_artist_name TEXT NOT NULL,
                artist_name TEXT NOT NULL,
                play_count INTEGER NOT NULL,
                meaningful_play_count INTEGER NOT NULL,
                skipped_count INTEGER NOT NULL,
                total_ms_played INTEGER NOT NULL
            )
            """)
        connection.exec_driver_sql("""
            CREATE TABLE spotify_vinyl_artist_matches (
                match_key TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                normalized_artist_name TEXT NOT NULL,
                artist_name TEXT NOT NULL,
                release_ids TEXT NOT NULL,
                release_count INTEGER NOT NULL,
                confidence_score INTEGER NOT NULL,
                match_type TEXT NOT NULL,
                explanation TEXT NOT NULL
            )
            """)
        connection.exec_driver_sql("""
            CREATE TABLE spotify_vinyl_release_matches (
                match_key TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                release_id TEXT NOT NULL,
                normalized_artist_name TEXT NOT NULL,
                normalized_album_name TEXT NOT NULL,
                spotify_artist_name TEXT NOT NULL,
                spotify_album_name TEXT NOT NULL,
                release_artist TEXT NOT NULL,
                release_title TEXT NOT NULL,
                confidence_score INTEGER NOT NULL,
                match_type TEXT NOT NULL,
                explanation TEXT NOT NULL
            )
            """)
        connection.exec_driver_sql("""
            INSERT INTO spotify_artist_stats (
                stat_key,
                user_id,
                normalized_artist_name,
                artist_name,
                play_count,
                meaningful_play_count,
                skipped_count,
                total_ms_played,
                first_played_at,
                last_played_at
            )
            VALUES (
                'user-a:rhythm-sound',
                'user-a',
                'rhythm sound',
                'Rhythm & Sound',
                4,
                3,
                1,
                720000,
                '2020-01-01T04:00:00+00:00',
                '2020-01-31T05:00:00+00:00'
            )
            """)
        connection.exec_driver_sql("""
            INSERT INTO spotify_hourly_stats (
                stat_key,
                user_id,
                played_hour,
                play_count,
                meaningful_play_count,
                skipped_count,
                total_ms_played
            )
            VALUES
                ('user-a:4', 'user-a', 4, 2, 2, 0, 360000),
                ('user-a:5', 'user-a', 5, 1, 1, 0, 180000),
                ('user-a:18', 'user-a', 18, 1, 0, 1, 45000)
            """)
        connection.exec_driver_sql("""
            INSERT INTO spotify_monthly_artist_stats (
                stat_key,
                user_id,
                played_year_month,
                normalized_artist_name,
                artist_name,
                play_count,
                meaningful_play_count,
                skipped_count,
                total_ms_played
            )
            VALUES (
                '2020-01:rhythm-sound',
                'user-a',
                '2020-01',
                'rhythm sound',
                'Rhythm & Sound',
                4,
                3,
                1,
                720000
            )
            """)
        connection.exec_driver_sql("""
            INSERT INTO spotify_vinyl_artist_matches (
                match_key,
                user_id,
                normalized_artist_name,
                artist_name,
                release_ids,
                release_count,
                confidence_score,
                match_type,
                explanation
            )
            VALUES (
                'user-a:rhythm-sound',
                'user-a',
                'rhythm sound',
                'Rhythm & Sound',
                '["release-1"]',
                1,
                100,
                'artist_exact',
                'Normalized Spotify artist matches a known release artist.'
            )
            """)
        connection.exec_driver_sql("""
            INSERT INTO spotify_vinyl_release_matches (
                match_key,
                user_id,
                release_id,
                normalized_artist_name,
                normalized_album_name,
                spotify_artist_name,
                spotify_album_name,
                release_artist,
                release_title,
                confidence_score,
                match_type,
                explanation
            )
            VALUES (
                'release-1:rhythm-sound:carrier',
                'user-a',
                'release-1',
                'rhythm sound',
                'carrier',
                'Rhythm & Sound',
                'Carrier',
                'Rhythm & Sound',
                'Carrier',
                100,
                'artist_album_exact',
                'Normalized Spotify artist and album match a known release.'
            )
            """)
