from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.ai.insight_tools import AiInsightToolRunner


def test_tool_runner_returns_grounded_collection_context() -> None:
    engine = create_engine("sqlite:///:memory:")
    session_factory = sessionmaker(bind=engine)
    _create_collection_tables(engine)

    with session_factory() as db:
        results = AiInsightToolRunner().run(db, message="What style did I play most lately?")

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
        results = AiInsightToolRunner().run(db, message="How are my mood and rating patterns?")

    assert [result.name for result in results] == [
        "get_listening_summary",
        "get_mood_distribution",
        "get_rating_distribution",
    ]
    rendered_context = "\n".join(result.content for result in results)
    assert "Focused: 2" in rendered_context
    assert "5: 2" in rendered_context


def _create_collection_tables(engine) -> None:
    with engine.begin() as connection:
        connection.exec_driver_sql("""
            CREATE TABLE releases (
                id TEXT PRIMARY KEY,
                discogs_release_id INTEGER NOT NULL,
                artist TEXT NOT NULL,
                title TEXT NOT NULL,
                label TEXT,
                year INTEGER,
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
        connection.exec_driver_sql("""
            INSERT INTO releases (id, discogs_release_id, artist, title, styles, created_at, updated_at)
            VALUES
                ('release-1', 101, 'Rhythm & Sound', 'Carrier',
                 '["Dub Techno", "Minimal"]', '2026-01-01', '2026-01-01'),
                ('release-2', 102, 'Moodymann', 'Silentintroduction',
                 '["House"]', '2026-01-01', '2026-01-01')
            """)
        connection.exec_driver_sql("""
            INSERT INTO sessions (id, release_id, rating, mood, played_at, vinyl_side, created_at)
            VALUES
                ('session-1', 'release-1', 5, 'Focused',
                 '2026-01-03T10:00:00+00:00', 'A', '2026-01-03T10:00:00+00:00'),
                ('session-2', 'release-1', 4, 'Focused',
                 '2026-01-02T10:00:00+00:00', 'B', '2026-01-02T10:00:00+00:00'),
                ('session-3', 'release-2', 5, 'Late Night',
                 '2026-01-01T10:00:00+00:00', 'A', '2026-01-01T10:00:00+00:00')
            """)
