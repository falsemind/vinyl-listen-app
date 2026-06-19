import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy import create_engine


def test_user_collection_scope_migration_backfills_legacy_rows(monkeypatch) -> None:
    migration = _load_migration()
    engine = create_engine("sqlite:///:memory:")
    monkeypatch.delenv(migration.LEGACY_OWNER_EMAIL_ENV, raising=False)

    with engine.begin() as connection:
        _create_tables(connection)
        _insert_user(connection, user_id="user-a", email="owner@example.com")
        _insert_release(connection, release_id="release-active", in_collection=True, is_favorite=True)
        _insert_release(
            connection,
            release_id="release-removed",
            in_collection=False,
            collection_removed_at="2026-06-01",
        )
        _insert_release(connection, release_id="release-plain", in_collection=False)
        connection.execute(sa.text("INSERT INTO collection_folders (id) VALUES (1)"))
        connection.execute(sa.text("INSERT INTO release_collection_folders (id) VALUES (1)"))
        connection.execute(sa.text("INSERT INTO collection_sync_jobs (id) VALUES ('job-1')"))

        owner_id = migration._resolve_legacy_owner_id(connection)
        migration._backfill_legacy_collection_memberships(connection, legacy_owner_id=owner_id)
        migration._backfill_legacy_owner_column(connection, table_name="collection_folders", legacy_owner_id=owner_id)
        migration._backfill_legacy_owner_column(
            connection, table_name="release_collection_folders", legacy_owner_id=owner_id
        )
        migration._backfill_legacy_owner_column(connection, table_name="collection_sync_jobs", legacy_owner_id=owner_id)

        memberships = connection.execute(sa.text("""
                SELECT release_id, in_collection, collection_removed_at, is_favorite
                FROM release_collection_memberships
                ORDER BY release_id
                """)).all()
        folder_owner = connection.execute(sa.text("SELECT user_id FROM collection_folders")).scalar_one()
        folder_membership_owner = connection.execute(
            sa.text("SELECT user_id FROM release_collection_folders")
        ).scalar_one()
        job_owner = connection.execute(sa.text("SELECT user_id FROM collection_sync_jobs")).scalar_one()

    assert owner_id == "user-a"
    assert [row.release_id for row in memberships] == ["release-active", "release-removed"]
    assert bool(memberships[0].in_collection) is True
    assert bool(memberships[0].is_favorite) is True
    assert bool(memberships[1].in_collection) is False
    assert memberships[1].collection_removed_at == "2026-06-01"
    assert folder_owner == "user-a"
    assert folder_membership_owner == "user-a"
    assert job_owner == "user-a"


def test_user_collection_scope_migration_uses_owner_email_env(monkeypatch) -> None:
    migration = _load_migration()
    engine = create_engine("sqlite:///:memory:")
    monkeypatch.setenv(migration.LEGACY_OWNER_EMAIL_ENV, "Owner-B@Example.com")

    with engine.begin() as connection:
        _create_tables(connection)
        _insert_user(connection, user_id="user-a", email="owner-a@example.com")
        _insert_user(connection, user_id="user-b", email="owner-b@example.com")
        _insert_release(connection, release_id="release-active", in_collection=True)

        owner_id = migration._resolve_legacy_owner_id(connection)

    assert owner_id == "user-b"


def test_user_collection_scope_migration_rejects_ambiguous_legacy_owner(monkeypatch) -> None:
    migration = _load_migration()
    engine = create_engine("sqlite:///:memory:")
    monkeypatch.delenv(migration.LEGACY_OWNER_EMAIL_ENV, raising=False)

    with engine.begin() as connection:
        _create_tables(connection)
        _insert_user(connection, user_id="user-a", email="owner-a@example.com")
        _insert_user(connection, user_id="user-b", email="owner-b@example.com")
        _insert_release(connection, release_id="release-active", in_collection=True)

        with pytest.raises(RuntimeError, match="multiple active accounts"):
            migration._resolve_legacy_owner_id(connection)


def _load_migration():
    migration_path = (
        Path(__file__).resolve().parents[2] / "alembic" / "versions" / "b7c8d9e0f1a2_add_user_collection_scope.py"
    )
    spec = importlib.util.spec_from_file_location("user_collection_scope_migration", migration_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _create_tables(connection) -> None:
    connection.execute(sa.text("""
            CREATE TABLE user_accounts (
                id TEXT PRIMARY KEY,
                normalized_email TEXT NOT NULL,
                is_active BOOLEAN NOT NULL,
                deleted_at TEXT,
                created_at TEXT NOT NULL
            )
            """))
    connection.execute(sa.text("""
            CREATE TABLE releases (
                id TEXT PRIMARY KEY,
                in_collection BOOLEAN NOT NULL,
                collection_added_at TEXT,
                collection_removed_at TEXT,
                last_discogs_sync_at TEXT,
                discogs_instance_id INTEGER,
                is_favorite BOOLEAN NOT NULL
            )
            """))
    connection.execute(sa.text("""
            CREATE TABLE release_collection_memberships (
                user_id TEXT NOT NULL,
                release_id TEXT NOT NULL,
                in_collection BOOLEAN NOT NULL,
                collection_added_at TEXT,
                collection_removed_at TEXT,
                last_discogs_sync_at TEXT,
                discogs_instance_id INTEGER,
                is_favorite BOOLEAN NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """))
    connection.execute(sa.text("CREATE TABLE collection_folders (id INTEGER PRIMARY KEY, user_id TEXT)"))
    connection.execute(sa.text("CREATE TABLE release_collection_folders (id INTEGER PRIMARY KEY, user_id TEXT)"))
    connection.execute(sa.text("CREATE TABLE collection_sync_jobs (id TEXT PRIMARY KEY, user_id TEXT)"))


def _insert_user(connection, *, user_id: str, email: str) -> None:
    connection.execute(
        sa.text("""
            INSERT INTO user_accounts (id, normalized_email, is_active, deleted_at, created_at)
            VALUES (:id, :normalized_email, TRUE, NULL, '2026-06-18T00:00:00Z')
            """),
        {"id": user_id, "normalized_email": email.lower()},
    )


def _insert_release(
    connection,
    *,
    release_id: str,
    in_collection: bool,
    is_favorite: bool = False,
    collection_removed_at: str | None = None,
) -> None:
    connection.execute(
        sa.text("""
            INSERT INTO releases (
                id,
                in_collection,
                collection_added_at,
                collection_removed_at,
                last_discogs_sync_at,
                discogs_instance_id,
                is_favorite
            )
            VALUES (
                :id,
                :in_collection,
                NULL,
                :collection_removed_at,
                NULL,
                NULL,
                :is_favorite
            )
            """),
        {
            "id": release_id,
            "in_collection": in_collection,
            "collection_removed_at": collection_removed_at,
            "is_favorite": is_favorite,
        },
    )
