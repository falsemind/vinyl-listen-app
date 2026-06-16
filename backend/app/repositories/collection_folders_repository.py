from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.collection_folders import CollectionFolder, ReleaseCollectionFolder
from app.models.releases import Releases


@dataclass(frozen=True)
class CollectionFolderData:
    discogs_folder_id: int
    name: str
    item_count: int | None
    is_default: bool


@dataclass(frozen=True)
class ReleaseFolderMembershipData:
    discogs_release_id: int
    discogs_instance_id: int | None
    date_added: datetime | None


class CollectionFoldersRepository:
    @staticmethod
    def list_folders(db: Session) -> Sequence[CollectionFolder]:
        return (
            db.query(CollectionFolder).order_by(CollectionFolder.is_default.desc(), CollectionFolder.name.asc()).all()
        )

    @staticmethod
    def upsert_folders(
        db: Session,
        folders: Sequence[CollectionFolderData],
        *,
        synced_at: datetime,
        commit: bool = True,
    ) -> dict[int, CollectionFolder]:
        existing = {
            folder.discogs_folder_id: folder
            for folder in db.query(CollectionFolder)
            .filter(CollectionFolder.discogs_folder_id.in_([folder.discogs_folder_id for folder in folders]))
            .all()
        }
        result: dict[int, CollectionFolder] = {}

        for folder_data in folders:
            folder = existing.get(folder_data.discogs_folder_id)
            if folder is None:
                folder = CollectionFolder(discogs_folder_id=folder_data.discogs_folder_id)

            folder.name = folder_data.name
            folder.item_count = folder_data.item_count
            folder.is_default = folder_data.is_default
            folder.last_discogs_sync_at = synced_at
            db.add(folder)
            result[folder_data.discogs_folder_id] = folder

        if commit:
            db.commit()
            for folder in result.values():
                db.refresh(folder)
        else:
            db.flush()
        return result

    @staticmethod
    def replace_folder_memberships(
        db: Session,
        *,
        folder: CollectionFolder,
        memberships: Sequence[ReleaseFolderMembershipData],
        synced_at: datetime,
        commit: bool = True,
    ) -> int:
        db.query(ReleaseCollectionFolder).filter(ReleaseCollectionFolder.collection_folder_id == folder.id).delete(
            synchronize_session=False
        )

        release_ids = {membership.discogs_release_id for membership in memberships}
        releases_by_discogs_id = {
            release.discogs_release_id: release
            for release in db.query(Releases).filter(Releases.discogs_release_id.in_(release_ids)).all()
        }

        inserted_count = 0
        for membership in memberships:
            release = releases_by_discogs_id.get(membership.discogs_release_id)
            if release is None:
                continue

            db.add(
                ReleaseCollectionFolder(
                    release_id=release.id,
                    collection_folder_id=folder.id,
                    discogs_instance_id=membership.discogs_instance_id,
                    date_added=membership.date_added,
                    last_discogs_sync_at=synced_at,
                )
            )
            inserted_count += 1

        if commit:
            db.commit()
        else:
            db.flush()
        return inserted_count
