from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.repositories.analytics_repository import AnalyticsRepository


def test_get_monthly_play_counts_uses_sqlite_month_expression() -> None:
    engine = create_engine("sqlite:///:memory:")
    session_factory = sessionmaker(bind=engine)

    with engine.begin() as connection:
        connection.exec_driver_sql(
            """
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
            """
        )
        connection.exec_driver_sql(
            """
            INSERT INTO sessions (id, release_id, played_at)
            VALUES
                ('session-1', 'release-1', '2026-01-02T10:00:00+00:00'),
                ('session-2', 'release-1', '2026-01-18T10:00:00+00:00'),
                ('session-3', 'release-2', '2026-02-03T10:00:00+00:00')
            """
        )

    with session_factory() as db:
        rows = AnalyticsRepository.get_monthly_play_counts(db)

    assert [(month, plays) for month, plays in rows] == [("2026-01", 2), ("2026-02", 1)]
