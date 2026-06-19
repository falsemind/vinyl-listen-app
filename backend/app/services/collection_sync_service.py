import logging
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.repositories.collection_folders_repository import (
    CollectionFolderData,
    CollectionFoldersRepository,
    ReleaseFolderMembershipData,
)
from app.repositories.collection_settings_repository import CollectionSettingsRepository
from app.repositories.releases_repository import ReleasesRepository
from app.schemas.collection import CollectionSourceOfTruth
from app.services.discogs_integration_service import DiscogsIntegrationService
from app.services.discogs_service import DiscogsApiConfig, DiscogsClient, DiscogsService
from app.services.release_mapper import InternalReleaseData, map_discogs_to_internal

logger = logging.getLogger(__name__)

CollectionProgressReporter = Callable[..., None]


class CollectionSyncError(Exception):
    """Raised when Discogs collection data cannot be reconciled."""


@dataclass(frozen=True)
class CollectionReleaseItem:
    discogs_release_id: int
    instance_id: int | None
    date_added: datetime | None
    basic_information: dict[str, Any]


@dataclass(frozen=True)
class CollectionFolderItem:
    discogs_folder_id: int
    name: str
    item_count: int | None
    is_default: bool


@dataclass(frozen=True)
class CollectionSyncResult:
    total_items: int
    unique_releases: int
    added_count: int
    updated_count: int
    removed_count: int


class CollectionSyncService:
    """Reconcile local collection membership with the user's Discogs collection."""

    def __init__(
        self,
        *,
        discogs_service: DiscogsService | None = None,
        discogs_service_factory: Callable[[str], DiscogsService] | None = None,
        discogs_integration_service: DiscogsIntegrationService | None = None,
        repository: ReleasesRepository | None = None,
        folder_repository: CollectionFoldersRepository | None = None,
        settings_repository: CollectionSettingsRepository | None = None,
        now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        self._discogs_service = discogs_service
        self._discogs_service_factory = discogs_service_factory or _build_discogs_service
        self._discogs_integration_service = discogs_integration_service or DiscogsIntegrationService()
        self._repository = repository or ReleasesRepository()
        self._folder_repository = folder_repository or CollectionFoldersRepository()
        self._settings_repository = settings_repository or CollectionSettingsRepository()
        self._now_provider = now_provider or (lambda: datetime.now(UTC))

    def sync_collection(
        self,
        db: Session,
        *,
        user_id: str,
        progress_reporter: CollectionProgressReporter | None = None,
    ) -> CollectionSyncResult:
        sync_started_at = self._now_provider()
        source_of_truth = self._settings_repository.get_source_of_truth(db, user_id=user_id)
        mirror_discogs_collection = source_of_truth == CollectionSourceOfTruth.DISCOGS
        _report_progress(progress_reporter, step="fetching", message="Fetching collection data")
        try:
            raw_items = self._fetch_discogs_collection_releases(db, user_id=user_id)
            collection_items = collapse_collection_items(raw_items)
            _report_progress(
                progress_reporter,
                step="importing",
                message="Importing data",
                total_items=len(raw_items),
                processed_items=0,
            )

            added_count = 0
            updated_count = 0
            active_discogs_release_ids: set[int] = set()

            for processed_count, item in enumerate(collection_items, start=1):
                release_data = _map_collection_item_to_release(item)
                release, created = self._repository.save_or_update(db, release_data, commit=False)
                has_membership_history = self._repository.has_collection_membership_history(
                    db, release=release, user_id=user_id
                )
                membership = self._repository.get_collection_membership(db, release_id=release.id, user_id=user_id)
                if _should_activate_import(
                    source_of_truth=source_of_truth,
                    in_collection=bool(membership and membership.in_collection),
                    created=created,
                    has_membership_history=has_membership_history,
                ):
                    self._repository.mark_in_collection(
                        db,
                        release,
                        user_id=user_id,
                        discogs_instance_id=item.instance_id,
                        collection_added_at=item.date_added,
                        synced_at=sync_started_at,
                        commit=False,
                    )
                active_discogs_release_ids.add(item.discogs_release_id)
                if created:
                    added_count += 1
                else:
                    updated_count += 1
                _report_progress(
                    progress_reporter,
                    step="importing",
                    message="Importing data",
                    total_items=len(raw_items),
                    processed_items=processed_count,
                    added_count=added_count,
                    updated_count=updated_count,
                )

            removed_count = 0
            if mirror_discogs_collection:
                removed_count = self._repository.mark_missing_collection_releases_removed(
                    db,
                    active_discogs_release_ids,
                    user_id=user_id,
                    removed_at=sync_started_at,
                    commit=False,
                )
            self._sync_collection_folders(db, user_id=user_id, raw_items=raw_items, synced_at=sync_started_at)
            db.commit()
            _report_progress(
                progress_reporter,
                step="finalizing",
                message="Finalizing collection sync",
                total_items=len(raw_items),
                processed_items=len(collection_items),
                added_count=added_count,
                updated_count=updated_count,
                removed_count=removed_count,
            )
        except Exception:
            db.rollback()
            raise

        logger.info(
            (
                "Discogs collection sync complete source_of_truth=%s total_items=%s "
                "unique_releases=%s added=%s updated=%s removed=%s"
            ),
            source_of_truth.value,
            len(raw_items),
            len(collection_items),
            added_count,
            updated_count,
            removed_count,
        )
        return CollectionSyncResult(
            total_items=len(raw_items),
            unique_releases=len(collection_items),
            added_count=added_count,
            updated_count=updated_count,
            removed_count=removed_count,
        )

    def _sync_collection_folders(
        self,
        db: Session,
        *,
        user_id: str,
        raw_items: list[dict[str, Any]],
        synced_at: datetime,
    ) -> None:
        folder_items = [
            _parse_collection_folder(folder) for folder in self._fetch_discogs_collection_folders(db, user_id=user_id)
        ]
        folder_records = self._folder_repository.upsert_folders(
            db,
            [
                CollectionFolderData(
                    discogs_folder_id=folder.discogs_folder_id,
                    name=folder.name,
                    item_count=folder.item_count,
                    is_default=folder.is_default,
                )
                for folder in folder_items
            ],
            user_id=user_id,
            synced_at=synced_at,
            commit=False,
        )

        for folder in folder_items:
            folder_record = folder_records[folder.discogs_folder_id]
            folder_raw_items = (
                raw_items
                if folder.is_default
                else self._fetch_discogs_collection_releases(db, user_id=user_id, folder_id=folder.discogs_folder_id)
            )
            self._folder_repository.replace_folder_memberships(
                db,
                user_id=user_id,
                folder=folder_record,
                memberships=_folder_memberships_from_items(folder_raw_items),
                synced_at=synced_at,
                commit=False,
            )

    def _fetch_discogs_collection_releases(
        self, db: Session, *, user_id: str, folder_id: int = 0
    ) -> list[dict[str, Any]]:
        if self._discogs_service is not None:
            return self._discogs_service.fetch_collection_releases(folder_id=folder_id)

        credentials = self._discogs_integration_service.get_saved_credentials(db, user_id=user_id)
        discogs_service = self._discogs_service_factory(credentials.access_token)
        return discogs_service.fetch_collection_releases(username=credentials.username, folder_id=folder_id)

    def _fetch_discogs_collection_folders(self, db: Session, *, user_id: str) -> list[dict[str, Any]]:
        if self._discogs_service is not None:
            return self._discogs_service.fetch_collection_folders()

        credentials = self._discogs_integration_service.get_saved_credentials(db, user_id=user_id)
        discogs_service = self._discogs_service_factory(credentials.access_token)
        return discogs_service.fetch_collection_folders(username=credentials.username)


def collapse_collection_items(items: Iterable[Mapping[str, Any]]) -> list[CollectionReleaseItem]:
    representatives: dict[int, CollectionReleaseItem] = {}

    for item in items:
        collection_item = _parse_collection_item(item)
        current = representatives.get(collection_item.discogs_release_id)
        if current is None or _is_better_representative(collection_item, current):
            representatives[collection_item.discogs_release_id] = collection_item

    return sorted(
        representatives.values(),
        key=lambda item: item.date_added or datetime.min.replace(tzinfo=UTC),
        reverse=True,
    )


def _build_discogs_service(access_token: str) -> DiscogsService:
    return DiscogsService(
        client=DiscogsClient(config=DiscogsApiConfig.from_token(access_token)),
    )


def _parse_collection_item(item: Mapping[str, Any]) -> CollectionReleaseItem:
    basic_information = item.get("basic_information")
    if not isinstance(basic_information, Mapping):
        raise CollectionSyncError("Discogs collection item is missing basic_information.")

    release_id = _coerce_int(basic_information.get("id")) or _coerce_int(item.get("id"))
    if release_id is None:
        raise CollectionSyncError("Discogs collection item is missing a release id.")

    release_payload = dict(basic_information)
    release_payload["id"] = release_id

    return CollectionReleaseItem(
        discogs_release_id=release_id,
        instance_id=_coerce_int(item.get("instance_id")),
        date_added=_parse_discogs_datetime(item.get("date_added")),
        basic_information=release_payload,
    )


def _parse_collection_folder(folder: Mapping[str, Any]) -> CollectionFolderItem:
    folder_id = _coerce_int(folder.get("id"))
    if folder_id is None:
        raise CollectionSyncError("Discogs collection folder is missing an id.")

    name = folder.get("name")
    if not isinstance(name, str) or not name.strip():
        name = f"Folder {folder_id}"

    return CollectionFolderItem(
        discogs_folder_id=folder_id,
        name=name.strip(),
        item_count=_coerce_int(folder.get("count")),
        is_default=folder_id == 0,
    )


def _folder_memberships_from_items(items: Iterable[Mapping[str, Any]]) -> list[ReleaseFolderMembershipData]:
    return [
        ReleaseFolderMembershipData(
            discogs_release_id=item.discogs_release_id,
            discogs_instance_id=item.instance_id,
            date_added=item.date_added,
        )
        for item in collapse_collection_items(items)
    ]


def _map_collection_item_to_release(item: CollectionReleaseItem) -> InternalReleaseData:
    try:
        return map_discogs_to_internal(item.basic_information)
    except ValueError as exc:
        raise CollectionSyncError(f"Discogs collection release {item.discogs_release_id} cannot be mapped.") from exc


def _should_activate_import(
    *,
    source_of_truth: CollectionSourceOfTruth,
    in_collection: bool,
    created: bool,
    has_membership_history: bool,
) -> bool:
    if source_of_truth == CollectionSourceOfTruth.DISCOGS:
        return True
    if created or in_collection:
        return True
    return not has_membership_history


def _is_better_representative(candidate: CollectionReleaseItem, current: CollectionReleaseItem) -> bool:
    if candidate.date_added and current.date_added:
        if candidate.date_added != current.date_added:
            return candidate.date_added > current.date_added
    elif candidate.date_added or current.date_added:
        return candidate.date_added is not None

    candidate_instance_id = candidate.instance_id if candidate.instance_id is not None else 2**63 - 1
    current_instance_id = current.instance_id if current.instance_id is not None else 2**63 - 1
    return candidate_instance_id < current_instance_id


def _parse_discogs_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None

    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


def _coerce_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return None
    return None


def _report_progress(progress_reporter: CollectionProgressReporter | None, **progress: int | str) -> None:
    if progress_reporter is not None:
        progress_reporter(**progress)
