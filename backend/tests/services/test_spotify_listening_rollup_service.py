from datetime import UTC, date, datetime

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.models.auth import UserAccount
from app.models.spotify_listening import (
    SpotifyAlbumStats,
    SpotifyArtistStats,
    SpotifyHourlyStats,
    SpotifyListeningEvent,
    SpotifyListeningImportBatch,
    SpotifyMonthlyArtistStats,
    SpotifySkipStats,
    SpotifyTrackStats,
    SpotifyVinylArtistMatch,
    SpotifyVinylReleaseMatch,
)
from app.repositories.spotify_listening_repository import SpotifyListeningRepository
from app.services.spotify_listening_rollup_service import SpotifyListeningRollupService


def _db_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    UserAccount.__table__.create(engine)
    with engine.begin() as connection:
        connection.execute(
            text("CREATE TABLE releases (id VARCHAR PRIMARY KEY, artist VARCHAR NOT NULL, title VARCHAR NOT NULL)")
        )
        connection.execute(text("""
                CREATE TABLE release_collection_memberships (
                    id INTEGER PRIMARY KEY,
                    user_id VARCHAR NOT NULL,
                    release_id VARCHAR NOT NULL,
                    in_collection BOOLEAN NOT NULL
                )
                """))
    SpotifyListeningImportBatch.__table__.create(engine)
    SpotifyListeningEvent.__table__.create(engine)
    SpotifyArtistStats.__table__.create(engine)
    SpotifyAlbumStats.__table__.create(engine)
    SpotifyTrackStats.__table__.create(engine)
    SpotifyHourlyStats.__table__.create(engine)
    SpotifyMonthlyArtistStats.__table__.create(engine)
    SpotifySkipStats.__table__.create(engine)
    SpotifyVinylArtistMatch.__table__.create(engine)
    SpotifyVinylReleaseMatch.__table__.create(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = session_factory()
    session.add_all(
        [
            UserAccount(
                id="user-a",
                email="user-a@example.com",
                password_hash="hash",
                normalized_email="user-a@example.com",
                password_hash_algorithm="argon2id",
                email_verified_at=None,
            ),
            UserAccount(
                id="user-b",
                email="user-b@example.com",
                password_hash="hash",
                normalized_email="user-b@example.com",
                password_hash_algorithm="argon2id",
                email_verified_at=None,
            ),
        ]
    )
    session.commit()
    return session


def test_refresh_builds_queryable_rollups_and_collection_matches() -> None:
    with _db_session() as db:
        db.execute(text("""
                INSERT INTO releases (id, artist, title)
                VALUES
                    ('release-1', 'Boards of Canada', 'Music Has the Right to Children'),
                    ('release-2', 'Boards of Canada', 'Geogaddi'),
                    ('release-3', 'Aphex Twin', 'Selected Ambient Works 85-92')
                """))
        db.execute(text("""
                INSERT INTO release_collection_memberships (user_id, release_id, in_collection)
                VALUES
                    ('user-a', 'release-1', TRUE),
                    ('user-a', 'release-2', TRUE),
                    ('user-a', 'release-3', TRUE),
                    ('user-b', 'release-3', TRUE)
                """))
        db.add_all(
            [
                _event(
                    event_key="event-1",
                    played_at=datetime(2019, 2, 3, 4, 5, 6, tzinfo=UTC),
                    ms_played=185000,
                    track_name="Roygbiv",
                    artist_name="Boards of Canada",
                    album_name="Music Has the Right to Children",
                    skipped=False,
                    reason_end="trackdone",
                ),
                _event(
                    event_key="event-2",
                    played_at=datetime(2019, 2, 3, 5, 5, 6, tzinfo=UTC),
                    ms_played=15000,
                    track_name="Roygbiv",
                    artist_name="Boards of Canada",
                    album_name="Music Has the Right to Children",
                    skipped=True,
                    reason_end="fwdbtn",
                ),
                _event(
                    event_key="event-3",
                    played_at=datetime(2019, 3, 1, 1, 0, 0, tzinfo=UTC),
                    ms_played=60000,
                    track_name="Xtal",
                    artist_name="Aphex Twin",
                    album_name="Selected Ambient Works 85-92",
                    skipped=False,
                    reason_end="trackdone",
                ),
            ]
        )
        db.commit()

        result = SpotifyListeningRollupService().refresh(db, user_id="user-a")

        assert result.artist_stats_count == 2
        assert result.album_stats_count == 2
        assert result.track_stats_count == 2
        assert result.hourly_stats_count == 3
        assert result.monthly_artist_stats_count == 2
        assert result.skip_stats_count == 2
        assert result.artist_match_count == 2
        assert result.release_match_count == 2

        repository = SpotifyListeningRepository()
        top_artist = repository.list_top_artists(db, user_id="user-a", limit=1)[0]
        assert top_artist.artist_name == "Boards of Canada"
        assert top_artist.play_count == 2
        assert top_artist.meaningful_play_count == 1
        assert top_artist.skipped_count == 1
        assert top_artist.total_ms_played == 200000

        top_album = repository.list_top_albums(db, user_id="user-a", limit=1)[0]
        assert top_album.album_name == "Music Has the Right to Children"
        assert top_album.play_count == 2

        hourly = {row.played_hour: row.play_count for row in repository.list_hourly_stats(db, user_id="user-a")}
        assert hourly == {1: 1, 4: 1, 5: 1}

        monthly = repository.list_monthly_artist_stats(
            db,
            user_id="user-a",
            normalized_artist_name="boards of canada",
        )
        assert len(monthly) == 1
        assert monthly[0].played_year_month == "2019-02"
        assert monthly[0].play_count == 2

        skipped = [row for row in repository.list_skip_stats(db, user_id="user-a") if row.skipped is True]
        assert len(skipped) == 1
        assert skipped[0].reason_end == "fwdbtn"

        artist_match = (
            db.query(SpotifyVinylArtistMatch)
            .filter_by(user_id="user-a", normalized_artist_name="boards of canada")
            .one_or_none()
        )
        assert artist_match is not None
        assert artist_match.release_ids == ["release-1", "release-2"]
        assert artist_match.confidence_score == 100
        assert artist_match.match_type == "artist_exact"
        assert "Exact normalized artist match" in artist_match.explanation

        release_match = repository.list_release_matches(db, user_id="user-a", limit=1)[0]
        assert release_match.release_id == "release-1"
        assert release_match.match_type == "artist_album_exact"
        assert "Exact normalized artist and album match" in release_match.explanation


def _event(
    *,
    event_key: str,
    played_at: datetime,
    ms_played: int,
    track_name: str,
    artist_name: str,
    album_name: str,
    skipped: bool,
    reason_end: str,
) -> SpotifyListeningEvent:
    normalized_track = _normalize(track_name)
    normalized_artist = _normalize(artist_name)
    normalized_album = _normalize(album_name)
    return SpotifyListeningEvent(
        user_id="user-a",
        import_batch_id=None,
        event_key=event_key,
        played_at=played_at,
        played_date=date(played_at.year, played_at.month, played_at.day),
        played_hour=played_at.hour,
        played_weekday=played_at.weekday(),
        played_year_month=f"{played_at.year:04d}-{played_at.month:02d}",
        ms_played=ms_played,
        conn_country="US",
        track_name=track_name,
        artist_name=artist_name,
        album_name=album_name,
        normalized_track_name=normalized_track,
        normalized_artist_name=normalized_artist,
        normalized_album_name=normalized_album,
        reason_start="trackdone",
        reason_end=reason_end,
        shuffle=False,
        skipped=skipped,
        offline=False,
        offline_timestamp=None,
        is_meaningful_listen=ms_played >= 30000,
    )


def _normalize(value: str) -> str:
    return value.casefold().replace("-", " ")
