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


def test_list_collection_releases_filters_cached_label_matches() -> None:
    engine = create_engine("sqlite:///:memory:")
    session_factory = sessionmaker(bind=engine)

    with engine.begin() as connection:
        _create_release_search_tables(connection)
        _insert_release(
            connection,
            discogs_release_id=1000,
            artist="Scientist",
            title="Wins The World Cup",
            label="Greensleeves",
        )
        _insert_release(
            connection,
            discogs_release_id=2000,
            artist="Various",
            title="Studio One Roots",
            label="Compilation",
            raw_discogs_json={
                "labels": [{"name": "Studio One"}, {"name": "Soul Jazz Records"}],
            },
        )
        _insert_release(
            connection,
            discogs_release_id=3000,
            artist="Unrelated",
            title="Elsewhere",
            label="Other",
        )

    with session_factory() as db:
        releases = ReleasesRepository.list_collection_releases(
            db,
            label="Studio One",
            limit=10,
            offset=0,
        )

    assert [release.title for release in releases] == ["Studio One Roots"]


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


def test_list_collection_releases_filters_by_discogs_folder_active_membership() -> None:
    engine = create_engine("sqlite:///:memory:")
    session_factory = sessionmaker(bind=engine)

    with engine.begin() as connection:
        _create_release_search_tables(connection)
        _insert_release(
            connection,
            discogs_release_id=1000,
            artist="Basic Channel",
            title="Shelf A",
        )
        _insert_release(
            connection,
            discogs_release_id=2000,
            artist="Basic Channel",
            title="Shelf B",
        )
        _insert_release(
            connection,
            discogs_release_id=3000,
            artist="Basic Channel",
            title="Removed Shelf A",
            in_collection=False,
        )
        _insert_collection_folder(connection, folder_pk=1, discogs_folder_id=123, name="Shelf A")
        _insert_collection_folder(connection, folder_pk=2, discogs_folder_id=456, name="Shelf B")
        _insert_release_collection_folder(connection, release_id="release-1000", folder_pk=1)
        _insert_release_collection_folder(connection, release_id="release-2000", folder_pk=2)
        _insert_release_collection_folder(connection, release_id="release-3000", folder_pk=1)

    with session_factory() as db:
        releases = ReleasesRepository.list_collection_releases(
            db,
            folder_id=123,
            include_removed=True,
            limit=10,
            offset=0,
        )
        total = ReleasesRepository.count_collection_releases(db, folder_id=123, include_removed=True)

    assert [release.title for release in releases] == ["Shelf A"]
    assert total == 1


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
    connection.exec_driver_sql("""
        CREATE TABLE collection_folders (
            id INTEGER PRIMARY KEY,
            discogs_folder_id INTEGER NOT NULL UNIQUE,
            name TEXT NOT NULL,
            item_count INTEGER,
            is_default BOOLEAN NOT NULL,
            last_discogs_sync_at TIMESTAMP,
            created_at TIMESTAMP,
            updated_at TIMESTAMP
        )
        """)
    connection.exec_driver_sql("""
        CREATE TABLE release_collection_folders (
            id INTEGER PRIMARY KEY,
            release_id TEXT NOT NULL,
            collection_folder_id INTEGER NOT NULL,
            discogs_instance_id INTEGER,
            date_added TIMESTAMP,
            last_discogs_sync_at TIMESTAMP,
            created_at TIMESTAMP,
            updated_at TIMESTAMP
        )
        """)


def _insert_release(
    connection: Connection,
    *,
    discogs_release_id: int,
    artist: str,
    title: str,
    raw_discogs_json: dict | None = None,
    label: str = "Label",
    is_favorite: bool = False,
    in_collection: bool = True,
) -> None:
    connection.exec_driver_sql(
        """
        INSERT INTO releases (
            id,
            discogs_release_id,
            artist,
            title,
            label,
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
            :label,
            :in_collection,
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
            "label": label,
            "is_favorite": is_favorite,
            "in_collection": in_collection,
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


def _insert_collection_folder(
    connection: Connection,
    *,
    folder_pk: int,
    discogs_folder_id: int,
    name: str,
) -> None:
    connection.exec_driver_sql(
        """
        INSERT INTO collection_folders (
            id,
            discogs_folder_id,
            name,
            is_default,
            created_at,
            updated_at
        )
        VALUES (
            :id,
            :discogs_folder_id,
            :name,
            0,
            '2026-06-05T10:00:00+00:00',
            '2026-06-05T10:00:00+00:00'
        )
        """,
        {
            "id": folder_pk,
            "discogs_folder_id": discogs_folder_id,
            "name": name,
        },
    )


def _insert_release_collection_folder(connection: Connection, *, release_id: str, folder_pk: int) -> None:
    connection.exec_driver_sql(
        """
        INSERT INTO release_collection_folders (
            release_id,
            collection_folder_id,
            created_at,
            updated_at
        )
        VALUES (
            :release_id,
            :collection_folder_id,
            '2026-06-05T10:00:00+00:00',
            '2026-06-05T10:00:00+00:00'
        )
        """,
        {
            "release_id": release_id,
            "collection_folder_id": folder_pk,
        },
    )
