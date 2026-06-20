import json

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
from app.services.spotify_listening_import_service import SpotifyListeningImportService, normalize_spotify_text


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
    session.add(
        UserAccount(
            id="user-a",
            email="user-a@example.com",
            password_hash="hash",
            normalized_email="user-a@example.com",
            password_hash_algorithm="argon2id",
            email_verified_at=None,
        )
    )
    session.commit()
    return session


def test_import_files_filters_spotify_export_fields_and_dedupes_events(tmp_path) -> None:
    spotify_file = tmp_path / "Streaming_History_Audio_2019.json"
    valid_song = {
        "ts": "2019-02-03 04:05:06",
        "username": "private-user",
        "platform": "not-retained",
        "ms_played": 185000,
        "conn_country": "US",
        "ip_addr_decrypted": "127.0.0.1",
        "user_agent_decrypted": "private-agent",
        "master_metadata_track_name": "Roygbiv",
        "master_metadata_album_artist_name": "Boards of Canada",
        "master_metadata_album_album_name": "Music Has the Right to Children",
        "spotify_track_uri": "spotify:track:not-retained",
        "reason_start": "trackdone",
        "reason_end": "trackdone",
        "shuffle": False,
        "skipped": False,
        "offline": True,
        "offline_timestamp": 1549170000000,
        "incognito_mode": False,
    }
    podcast_item = {
        "ts": "2019-02-03 05:05:06",
        "episode_name": "Out of scope",
        "episode_show_name": "Podcast",
        "ms_played": 120000,
    }
    spotify_file.write_text(json.dumps([valid_song, valid_song, podcast_item]), encoding="utf-8")

    with _db_session() as db:
        result = SpotifyListeningImportService().import_files(db, [spotify_file], user_id="user-a", batch_size=1)

        assert result.total_items == 3
        assert result.imported_count == 1
        assert result.duplicate_count == 1
        assert result.skipped_count == 1
        assert result.error_count == 0

        event = db.query(SpotifyListeningEvent).one()
        assert event.user_id == "user-a"
        assert event.track_name == "Roygbiv"
        assert event.artist_name == "Boards of Canada"
        assert event.normalized_artist_name == "boards of canada"
        assert event.normalized_album_name == "music has the right to children"
        assert event.played_year_month == "2019-02"
        assert event.played_hour == 4
        assert event.played_weekday == 6
        assert event.is_meaningful_listen is True
        assert event.offline_timestamp == "1549170000000"

        assert not hasattr(event, "username")
        assert not hasattr(event, "platform")
        assert not hasattr(event, "spotify_track_uri")
        assert not hasattr(event, "incognito_mode")

        batch = db.get(SpotifyListeningImportBatch, result.batch_id)
        assert batch is not None
        assert batch.user_id == "user-a"
        assert batch.status == "completed"
        assert batch.source_paths == [str(spotify_file)]
        assert db.query(SpotifyArtistStats).count() == 1
        assert db.query(SpotifyAlbumStats).count() == 1
        assert db.query(SpotifyTrackStats).count() == 1
        assert db.query(SpotifyHourlyStats).count() == 1


def test_import_files_records_item_errors_without_stopping_import(tmp_path) -> None:
    spotify_file = tmp_path / "Streaming_History_Audio_2020.json"
    spotify_file.write_text(
        json.dumps(
            [
                {
                    "ts": "not-a-date",
                    "ms_played": 1000,
                    "master_metadata_track_name": "Track",
                    "master_metadata_album_artist_name": "Artist",
                    "master_metadata_album_album_name": "Album",
                },
                {
                    "ts": "2020-01-01T01:00:00Z",
                    "ms_played": 1000,
                    "master_metadata_track_name": "Short Play",
                    "master_metadata_album_artist_name": "Artist",
                    "master_metadata_album_album_name": "Album",
                },
            ]
        ),
        encoding="utf-8",
    )

    with _db_session() as db:
        result = SpotifyListeningImportService().import_files(db, [spotify_file], user_id="user-a")

        assert result.total_items == 2
        assert result.imported_count == 1
        assert result.skipped_count == 1
        assert result.error_count == 1
        assert result.error_summary == ["item 1: ts is invalid: not-a-date"]

        event = db.query(SpotifyListeningEvent).one()
        assert event.is_meaningful_listen is False


def test_normalize_spotify_text_collapses_case_punctuation_and_spacing() -> None:
    assert normalize_spotify_text("  Boards-of   Canada!!! ") == "boards of canada"
