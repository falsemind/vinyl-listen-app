import logging
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.repositories.releases_repository import ReleasesRepository
from app.services.discogs_service import DiscogsService
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
        repository: ReleasesRepository | None = None,
        now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        self._discogs_service = discogs_service or DiscogsService()
        self._repository = repository or ReleasesRepository()
        self._now_provider = now_provider or (lambda: datetime.now(UTC))

    def sync_collection(
        self,
        db: Session,
        *,
        progress_reporter: CollectionProgressReporter | None = None,
    ) -> CollectionSyncResult:
        sync_started_at = self._now_provider()
        _report_progress(progress_reporter, step="fetching", message="Fetching collection data")
        raw_items = self._discogs_service.fetch_collection_releases()
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
            release, created = self._repository.save_or_update(db, release_data)
            self._repository.mark_in_collection(
                db,
                release,
                discogs_instance_id=item.instance_id,
                collection_added_at=item.date_added,
                synced_at=sync_started_at,
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

        removed_count = self._repository.mark_missing_collection_releases_removed(
            db,
            active_discogs_release_ids,
            removed_at=sync_started_at,
        )
        _report_progress(
            progress_reporter,
            step="loading",
            message="Loading...",
            total_items=len(raw_items),
            processed_items=len(collection_items),
            added_count=added_count,
            updated_count=updated_count,
            removed_count=removed_count,
        )

        logger.info(
            "Discogs collection sync complete total_items=%s unique_releases=%s added=%s updated=%s removed=%s",
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


def _map_collection_item_to_release(item: CollectionReleaseItem) -> InternalReleaseData:
    try:
        return map_discogs_to_internal(item.basic_information)
    except ValueError as exc:
        raise CollectionSyncError(f"Discogs collection release {item.discogs_release_id} cannot be mapped.") from exc


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
