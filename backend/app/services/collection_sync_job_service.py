import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy.orm import Session

from app.database.db import SessionLocal
from app.models.collection_sync_job import CollectionSyncJob
from app.repositories.collection_sync_job_repository import CollectionSyncJobRepository
from app.schemas.collection import CollectionSyncJobStatusResponse
from app.services.collection_sync_service import CollectionSyncError, CollectionSyncService
from app.services.discogs_integration_service import DiscogsIntegrationService
from app.services.discogs_service import DiscogsClientError, DiscogsConfigurationError

logger = logging.getLogger(__name__)

DEFAULT_COLLECTION_SYNC_JOB_TTL = timedelta(hours=1)
DEFAULT_COLLECTION_SYNC_STALE_ACTIVE_JOB_TIMEOUT = timedelta(minutes=30)


class CollectionSyncJobNotFoundError(Exception):
    """Raised when a collection sync job id does not exist."""


class CollectionSyncConfigurationError(Exception):
    status_code = 500
    code = "discogs_config_missing"
    message = "Discogs collection sync is not configured."


@dataclass(frozen=True)
class CollectionSyncJobFailure:
    code: str
    message: str
    failed_step: str


class CollectionSyncJobService:
    def __init__(
        self,
        *,
        sync_service: CollectionSyncService | None = None,
        discogs_integration_service: DiscogsIntegrationService | None = None,
        repository: CollectionSyncJobRepository | None = None,
        session_factory: Callable[[], Session] = SessionLocal,
        now_provider: Callable[[], datetime] | None = None,
        job_ttl: timedelta = DEFAULT_COLLECTION_SYNC_JOB_TTL,
        stale_active_job_timeout: timedelta = DEFAULT_COLLECTION_SYNC_STALE_ACTIVE_JOB_TIMEOUT,
        require_discogs_config: bool = True,
    ) -> None:
        self._sync_service = sync_service or CollectionSyncService()
        self._discogs_integration_service = discogs_integration_service or DiscogsIntegrationService()
        self._repository = repository or CollectionSyncJobRepository()
        self._session_factory = session_factory
        self._now_provider = now_provider or (lambda: datetime.now(UTC))
        self._service_started_at = self._now_provider()
        self._job_ttl = job_ttl
        self._stale_active_job_timeout = stale_active_job_timeout
        self._require_discogs_config = require_discogs_config

    def create_job(self, db: Session) -> CollectionSyncJobStatusResponse:
        if self._require_discogs_config:
            self._validate_discogs_config(db)

        created_at = self._now_provider()
        self._expire_stale_active_jobs(db, now=created_at)
        job = self._repository.create(
            db,
            job_id=str(uuid4()),
            status="queued",
            message="Collection sync queued",
            created_at=created_at,
            expires_at=created_at + self._job_ttl,
        )
        return self._to_response(job)

    def get_job(self, db: Session, job_id: str) -> CollectionSyncJobStatusResponse:
        self._expire_stale_active_jobs(db, now=self._now_provider())
        job = self._repository.get(db, job_id)
        if job is None:
            raise CollectionSyncJobNotFoundError(job_id)
        return self._to_response(job)

    def get_active_job(self, db: Session) -> CollectionSyncJobStatusResponse | None:
        self._expire_stale_active_jobs(db, now=self._now_provider())
        job = self._repository.get_active(db)
        if job is None:
            return None
        return self._to_response(job)

    def process_job(self, job_id: str) -> None:
        with self._session_factory() as db:
            job = self._repository.get(db, job_id)
            if job is None:
                logger.warning("Collection sync job disappeared before processing job_id=%s", job_id)
                return

        try:
            with self._session_factory() as db:
                result = self._sync_service.sync_collection(
                    db,
                    progress_reporter=lambda **progress: self._update_progress(job_id, **progress),
                )
        except Exception as error:  # noqa: BLE001
            self._fail_job(job_id, self._map_failure(error))
            return

        with self._session_factory() as db:
            job = self._repository.get(db, job_id)
            if job is None:
                logger.warning("Collection sync job disappeared before completion job_id=%s", job_id)
                return

            self._repository.complete(
                db,
                job,
                message="Collection sync complete",
                updated_at=self._now_provider(),
                total_items=result.total_items,
                processed_items=result.unique_releases,
                added_count=result.added_count,
                updated_count=result.updated_count,
                removed_count=result.removed_count,
            )

    def _update_progress(
        self,
        job_id: str,
        *,
        step: str,
        message: str,
        total_items: int | None = None,
        processed_items: int | None = None,
        added_count: int | None = None,
        updated_count: int | None = None,
        removed_count: int | None = None,
    ) -> None:
        with self._session_factory() as db:
            job = self._repository.get(db, job_id)
            if job is None:
                logger.warning("Collection sync job disappeared before progress update job_id=%s", job_id)
                return

            self._repository.update_progress(
                db,
                job,
                step=step,
                message=message,
                updated_at=self._now_provider(),
                total_items=total_items,
                processed_items=processed_items,
                added_count=added_count,
                updated_count=updated_count,
                removed_count=removed_count,
            )

    def _fail_job(self, job_id: str, failure: CollectionSyncJobFailure) -> None:
        with self._session_factory() as db:
            job = self._repository.get(db, job_id)
            if job is None:
                logger.warning("Collection sync job disappeared before failure update job_id=%s", job_id)
                return

            self._repository.fail(
                db,
                job,
                error={
                    "code": failure.code,
                    "message": failure.message,
                    "failed_step": failure.failed_step,
                },
                message=failure.message,
                updated_at=self._now_provider(),
            )

    def _map_failure(self, error: Exception) -> CollectionSyncJobFailure:
        if isinstance(error, DiscogsConfigurationError):
            return CollectionSyncJobFailure(
                code="discogs_config_missing",
                message="Discogs collection sync is not configured.",
                failed_step="fetching",
            )
        if isinstance(error, DiscogsClientError):
            return CollectionSyncJobFailure(
                code="discogs_unavailable",
                message=str(error),
                failed_step="fetching",
            )
        if isinstance(error, CollectionSyncError):
            return CollectionSyncJobFailure(
                code="collection_sync_failed",
                message=str(error),
                failed_step="importing",
            )

        logger.exception("Unexpected collection sync failure")
        return CollectionSyncJobFailure(
            code="collection_sync_failed",
            message="Collection sync failed.",
            failed_step="unknown",
        )

    def _validate_discogs_config(self, db: Session) -> None:
        if not self._discogs_integration_service.get_status(db).access_token_saved:
            raise CollectionSyncConfigurationError()

    def _expire_stale_active_jobs(self, db: Session, *, now: datetime) -> int:
        if self._stale_active_job_timeout.total_seconds() <= 0:
            return 0

        stale_before = max(
            now - self._stale_active_job_timeout,
            self._service_started_at - timedelta(microseconds=1),
        )
        return self._repository.expire_stale_active(
            db,
            stale_before=stale_before,
            expires_at_or_before=now,
            updated_at=now,
        )

    def _to_response(self, job: CollectionSyncJob) -> CollectionSyncJobStatusResponse:
        return CollectionSyncJobStatusResponse(
            job_id=job.id,
            status=job.status,
            step=job.step,
            message=job.message,
            total_items=job.total_items,
            processed_items=job.processed_items,
            added_count=job.added_count,
            updated_count=job.updated_count,
            removed_count=job.removed_count,
            error=job.error,
            created_at=job.created_at,
            updated_at=job.updated_at,
        )
