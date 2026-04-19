from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.releases import Releases
from app.repositories.releases_repository import ReleasesRepository
from app.services.discogs_service import DiscogsService
from app.services.release_mapper import InternalReleaseData, map_discogs_to_internal


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
        raw_payload = self._discogs_service.fetch_release(
            db,
            discogs_release_id,
            force_refresh=force_refresh,
        )
        release_data = map_discogs_to_internal(raw_payload)
        release, created = self._repository.save_or_update(db, release_data)
        return ReleaseImportResult(release=release, created=created)

    def get_release(self, db: Session, release_id: str) -> Releases | None:
        return self._repository.get_by_id(db, release_id)

    def map_discogs_payload(self, raw_payload: dict) -> InternalReleaseData:
        return map_discogs_to_internal(raw_payload)
