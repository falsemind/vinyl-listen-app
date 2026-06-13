import json

from sqlalchemy import create_engine
from sqlalchemy.engine import Connection
from sqlalchemy.orm import sessionmaker

from app.repositories.releases_repository import ReleasesRepository


def test_search_collection_releases_paginates_cached_track_artist_matches() -> None:
    engine = create_engine("sqlite:///:memory:")
    session_factory = sessionmaker(bind=engine)

    with engine.begin() as connection:
        _create_release_search_tables(connection)
        for index in range(10):
            _insert_release(
                connection,
                discogs_release_id=1000 + index,
                artist="Target Artist",
                title=f"Release {index:02d}",
            )
        _insert_release(
            connection,
            discogs_release_id=2000,
            artist="Various",
            title="Remix Collection",
            raw_discogs_json={
                "tracklist": [
                    {
                        "title": "Late Night Tune (Target Artist Remix)",
                        "extraartists": [{"name": "Target Artist", "role": "Remix"}],
                    }
                ]
            },
        )

    with session_factory() as db:
        first_page = ReleasesRepository.search_collection_releases(
            db,
            artist="Target Artist",
            limit=10,
            offset=0,
        )
        second_page = ReleasesRepository.search_collection_releases(
            db,
            artist="Target Artist",
            limit=10,
            offset=10,
        )

    assert len(first_page) == 10
    assert [release.title for release in second_page] == ["Remix Collection"]


def test_list_collection_releases_filters_cached_artist_matches() -> None:
    engine = create_engine("sqlite:///:memory:")
    session_factory = sessionmaker(bind=engine)

    with engine.begin() as connection:
        _create_release_search_tables(connection)
        _insert_release(
            connection,
            discogs_release_id=1000,
            artist="Basic Channel",
            title="BCD",
        )
        _insert_release(
            connection,
            discogs_release_id=2000,
            artist="Various",
            title="Maurizio Mix",
            raw_discogs_json={
                "artists": [{"name": "Maurizio"}, {"name": "Basic Channel"}],
            },
        )
        _insert_release(
            connection,
            discogs_release_id=3000,
            artist="Unrelated",
            title="Elsewhere",
        )

    with session_factory() as db:
        releases = ReleasesRepository.list_collection_releases(
            db,
            artist="Maurizio",
            limit=10,
            offset=0,
        )

    assert [release.title for release in releases] == ["Maurizio Mix"]


def test_list_collection_releases_filters_favorites() -> None:
    engine = create_engine("sqlite:///:memory:")
    session_factory = sessionmaker(bind=engine)

    with engine.begin() as connection:
        _create_release_search_tables(connection)
        _insert_release(
            connection,
            discogs_release_id=1000,
            artist="Basic Channel",
            title="Favorite",
            is_favorite=True,
        )
        _insert_release(
            connection,
            discogs_release_id=2000,
            artist="Basic Channel",
            title="Regular",
        )

    with session_factory() as db:
        releases = ReleasesRepository.list_collection_releases(
            db,
            favorite=True,
            limit=10,
            offset=0,
        )

    assert [release.title for release in releases] == ["Favorite"]


def _create_release_search_tables(connection: Connection) -> None:
    connection.exec_driver_sql("""
        CREATE TABLE releases (
            id TEXT PRIMARY KEY,
            discogs_release_id INTEGER NOT NULL UNIQUE,
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
            in_collection BOOLEAN NOT NULL,
            collection_added_at TIMESTAMP,
            collection_removed_at TIMESTAMP,
            last_discogs_sync_at TIMESTAMP,
            discogs_instance_id INTEGER,
            is_favorite BOOLEAN NOT NULL,
            created_at TIMESTAMP,
            updated_at TIMESTAMP
        )
        """)
    connection.exec_driver_sql("""
        CREATE TABLE discogs_release_cache (
            discogs_release_id INTEGER PRIMARY KEY,
            raw_discogs_json TEXT NOT NULL,
            cached_at TIMESTAMP,
            last_accessed_at TIMESTAMP
        )
        """)


def _insert_release(
    connection: Connection,
    *,
    discogs_release_id: int,
    artist: str,
    title: str,
    raw_discogs_json: dict | None = None,
    is_favorite: bool = False,
) -> None:
    connection.exec_driver_sql(
        """
        INSERT INTO releases (
            id,
            discogs_release_id,
            artist,
            title,
            in_collection,
            is_favorite,
            created_at,
            updated_at
        )
        VALUES (
            :id,
            :discogs_release_id,
            :artist,
            :title,
            1,
            :is_favorite,
            '2026-06-05T10:00:00+00:00',
            '2026-06-05T10:00:00+00:00'
        )
        """,
        {
            "id": f"release-{discogs_release_id}",
            "discogs_release_id": discogs_release_id,
            "artist": artist,
            "title": title,
            "is_favorite": is_favorite,
        },
    )
    if raw_discogs_json is None:
        return

    connection.exec_driver_sql(
        """
        INSERT INTO discogs_release_cache (
            discogs_release_id,
            raw_discogs_json,
            cached_at
        )
        VALUES (
            :discogs_release_id,
            :raw_discogs_json,
            '2026-06-05T10:00:00+00:00'
        )
        """,
        {
            "discogs_release_id": discogs_release_id,
            "raw_discogs_json": json.dumps(raw_discogs_json),
        },
    )
