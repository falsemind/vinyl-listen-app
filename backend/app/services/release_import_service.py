import logging
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.releases import Releases
from app.repositories.discogs_release_repository import DiscogsReleaseRepository
from app.repositories.releases_repository import ReleasesRepository
from app.services.discogs_integration_service import DiscogsIntegrationService
from app.services.discogs_service import DiscogsService
from app.services.release_mapper import (
    InternalReleaseData,
    ReleaseArtistData,
    ReleaseSideOptionData,
    ReleaseTrackData,
    extract_release_artists,
    extract_release_side_options,
    extract_release_sides,
    extract_release_tracklist,
    map_discogs_to_internal,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ReleaseImportResult:
    release: Releases
    created: bool

    @property
    def status(self) -> str:
        return "created" if self.created else "updated"


class ReleaseImportService:
    def __init__(
        self,
        discogs_service: DiscogsService | None = None,
        discogs_integration_service: DiscogsIntegrationService | None = None,
        repository: ReleasesRepository | None = None,
        discogs_repository: DiscogsReleaseRepository | None = None,
    ) -> None:
        self._discogs_service = discogs_service
        self._discogs_integration_service = discogs_integration_service or DiscogsIntegrationService()
        self._repository = repository or ReleasesRepository()
        self._discogs_repository = discogs_repository or DiscogsReleaseRepository()

    def import_release(
        self,
        db: Session,
        discogs_release_id: int,
        *,
        user_id: str | None = None,
        force_refresh: bool = False,
    ) -> ReleaseImportResult:
        logger.info(
            "Importing release discogs_release_id=%s force_refresh=%s",
            discogs_release_id,
            force_refresh,
        )
        discogs_service = self._discogs_service or self._build_discogs_service_for_import(db, user_id=user_id)
        raw_payload = discogs_service.fetch_release(
            db,
            discogs_release_id,
            force_refresh=force_refresh,
        )
        release_data = map_discogs_to_internal(raw_payload)
        release, created = self._repository.save_or_update(db, release_data)
        logger.info(
            "Imported release discogs_release_id=%s release_id=%s created=%s",
            discogs_release_id,
            release.id,
            created,
        )
        return ReleaseImportResult(release=release, created=created)

    def import_release_to_collection(
        self,
        db: Session,
        discogs_release_id: int,
        *,
        user_id: str,
        force_refresh: bool = False,
    ) -> ReleaseImportResult:
        result = self.import_release(
            db,
            discogs_release_id,
            user_id=user_id,
            force_refresh=force_refresh,
        )
        synced_at = datetime.now(UTC)
        self._repository.mark_in_collection(
            db,
            result.release,
            user_id=user_id,
            discogs_instance_id=None,
            collection_added_at=synced_at,
            synced_at=synced_at,
        )
        return result

    def _build_discogs_service_for_import(self, db: Session, *, user_id: str | None = None) -> DiscogsService:
        return self._discogs_integration_service.build_discogs_service(db, user_id=user_id)

    def import_client_discogs_release(
        self,
        db: Session,
        raw_payload: dict,
    ) -> ReleaseImportResult:
        release_data = map_discogs_to_internal(raw_payload)
        self._discogs_repository.upsert(
            db,
            discogs_release_id=release_data.discogs_release_id,
            raw_discogs_json=raw_payload,
        )
        release, created = self._repository.save_or_update(db, release_data)
        logger.info(
            "Imported client-provided Discogs release discogs_release_id=%s release_id=%s created=%s",
            release_data.discogs_release_id,
            release.id,
            created,
        )
        return ReleaseImportResult(release=release, created=created)

    def get_release(self, db: Session, release_id: str) -> Releases | None:
        logger.info("Loading release release_id=%s", release_id)
        release = self._repository.get_by_id(db, release_id)
        if release is None:
            logger.debug("Release not found in Discogs-backed releases release_id=%s", release_id)
        return release

    def refresh_release(
        self,
        db: Session,
        release_id: str,
        *,
        user_id: str | None = None,
    ) -> ReleaseImportResult | None:
        release = self.get_release(db, release_id)
        if release is None:
            return None
        return self.import_release(db, release.discogs_release_id, user_id=user_id, force_refresh=True)

    def has_full_discogs_info(self, db: Session, discogs_release_id: int) -> bool:
        return self._discogs_repository.get_by_discogs_release_id(db, discogs_release_id) is not None

    def get_available_sides(self, db: Session, discogs_release_id: int) -> list[str]:
        cache_entry = self._discogs_repository.get_by_discogs_release_id(db, discogs_release_id)
        return extract_release_sides(cache_entry.raw_discogs_json if cache_entry is not None else None)

    def get_available_side_options(self, db: Session, discogs_release_id: int) -> list[ReleaseSideOptionData]:
        cache_entry = self._discogs_repository.get_by_discogs_release_id(db, discogs_release_id)
        return extract_release_side_options(cache_entry.raw_discogs_json if cache_entry is not None else None)

    def get_tracklist(self, db: Session, discogs_release_id: int) -> list[ReleaseTrackData]:
        cache_entry = self._discogs_repository.get_by_discogs_release_id(db, discogs_release_id)
        return extract_release_tracklist(cache_entry.raw_discogs_json if cache_entry is not None else None)

    def get_artists(self, db: Session, discogs_release_id: int) -> list[ReleaseArtistData]:
        cache_entry = self._discogs_repository.get_by_discogs_release_id(db, discogs_release_id)
        return extract_release_artists(cache_entry.raw_discogs_json if cache_entry is not None else None)

    def map_discogs_payload(self, raw_payload: dict) -> InternalReleaseData:
        logger.debug("Mapping Discogs payload to internal release model")
        return map_discogs_to_internal(raw_payload)
