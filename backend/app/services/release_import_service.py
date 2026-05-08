import logging
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.releases import Releases
from app.repositories.releases_repository import ReleasesRepository
from app.services.discogs_service import DiscogsService
from app.services.release_mapper import InternalReleaseData, map_discogs_to_internal

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
        repository: ReleasesRepository | None = None,
    ) -> None:
        self._discogs_service = discogs_service or DiscogsService()
        self._repository = repository or ReleasesRepository()

    def import_release(
        self,
        db: Session,
        discogs_release_id: int,
        *,
        force_refresh: bool = False,
    ) -> ReleaseImportResult:
        logger.info(
            "Importing release discogs_release_id=%s force_refresh=%s",
            discogs_release_id,
            force_refresh,
        )
        raw_payload = self._discogs_service.fetch_release(
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

    def get_release(self, db: Session, release_id: str) -> Releases | None:
        logger.info("Loading release release_id=%s", release_id)
        release = self._repository.get_by_id(db, release_id)
        if release is None:
            logger.info("Release not found release_id=%s", release_id)
        return release

    def map_discogs_payload(self, raw_payload: dict) -> InternalReleaseData:
        logger.debug("Mapping Discogs payload to internal release model")
        return map_discogs_to_internal(raw_payload)
