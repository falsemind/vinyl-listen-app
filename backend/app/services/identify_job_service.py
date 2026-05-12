import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy.orm import Session

from app.database.db import SessionLocal
from app.models.identify_job import IdentifyJob
from app.repositories.identify_job_repository import IdentifyJobRepository
from app.schemas.identify import (
    IdentifyCandidateResponse,
    IdentifyJobError,
    IdentifyJobStatus,
    IdentifyJobStatusResponse,
    IdentifyResponse,
)
from app.services.discogs_service import DiscogsClientError
from app.services.identify_service import IdentifyResult, IdentifyService, IdentifyValidationError

logger = logging.getLogger(__name__)

DEFAULT_IDENTIFY_JOB_TTL = timedelta(hours=24)


class IdentifyJobNotFoundError(Exception):
    pass


class IdentifyJobExpiredError(Exception):
    pass


@dataclass(frozen=True)
class IdentifyJobFailure:
    code: str
    message: str
    failed_step: str


class DatabaseIdentifyProgressReporter:
    def __init__(
        self,
        *,
        db: Session,
        job: IdentifyJob,
        repository: IdentifyJobRepository,
        now_provider: Callable[[], datetime],
    ) -> None:
        self._db = db
        self._job = job
        self._repository = repository
        self._now_provider = now_provider

    def update(self, status: str, message: str) -> None:
        self._job = self._repository.update_status(
            self._db,
            self._job,
            status=status,
            message=message,
            updated_at=self._now_provider(),
        )


class IdentifyJobService:
    def __init__(
        self,
        *,
        identify_service: IdentifyService | None = None,
        repository: IdentifyJobRepository | None = None,
        session_factory: Callable[[], Session] = SessionLocal,
        now_provider: Callable[[], datetime] | None = None,
        job_ttl: timedelta = DEFAULT_IDENTIFY_JOB_TTL,
    ) -> None:
        self._identify_service = identify_service or IdentifyService()
        self._repository = repository or IdentifyJobRepository()
        self._session_factory = session_factory
        self._now_provider = now_provider or (lambda: datetime.now(UTC))
        self._job_ttl = job_ttl

    def create_job(
        self,
        db: Session,
        *,
        image_bytes: bytes,
        filename: str,
        content_type: str,
    ) -> IdentifyJobStatusResponse:
        self._identify_service.validate_upload(
            image_bytes=image_bytes,
            filename=filename,
            content_type=content_type,
        )
        now = self._now_provider()
        job = self._repository.create(
            db,
            job_id=str(uuid4()),
            status=IdentifyJobStatus.UPLOAD_RECEIVED.value,
            message="Image upload received",
            filename=filename,
            content_type=content_type,
            created_at=now,
            expires_at=now + self._job_ttl,
        )
        return self._to_response(job)

    def get_job(self, db: Session, job_id: str) -> IdentifyJobStatusResponse:
        job = self._repository.get(db, job_id)
        if job is None:
            raise IdentifyJobNotFoundError(job_id)
        if _ensure_utc(job.expires_at) <= self._now_provider():
            raise IdentifyJobExpiredError(job_id)
        return self._to_response(job)

    def process_job(self, job_id: str, *, image_bytes: bytes, filename: str, content_type: str) -> None:
        with self._session_factory() as db:
            job = self._repository.get(db, job_id)
            if job is None:
                logger.warning("Identify job disappeared before processing job_id=%s", job_id)
                return

            progress_reporter = DatabaseIdentifyProgressReporter(
                db=db,
                job=job,
                repository=self._repository,
                now_provider=self._now_provider,
            )

            try:
                result = self._identify_service.identify(
                    db,
                    image_bytes=image_bytes,
                    filename=filename,
                    content_type=content_type,
                    progress_reporter=progress_reporter,
                )
            except Exception as error:  # noqa: BLE001
                job = self._repository.get(db, job_id)
                failure = _map_exception_to_failure(error, job.status if job else None)
                logger.exception("Identify job failed job_id=%s code=%s", job_id, failure.code)
                if job is not None:
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
                return

            job = self._repository.get(db, job_id)
            if job is None:
                logger.warning("Identify job disappeared before completion job_id=%s", job_id)
                return
            self._repository.complete(
                db,
                job,
                result=_identify_result_to_payload(result),
                message="Identify completed",
                updated_at=self._now_provider(),
            )

    def _to_response(self, job: IdentifyJob) -> IdentifyJobStatusResponse:
        result = IdentifyResponse.model_validate(job.result) if job.result else None
        error = IdentifyJobError.model_validate(job.error) if job.error else None
        return IdentifyJobStatusResponse(
            job_id=job.id,
            status=IdentifyJobStatus(job.status),
            message=job.message,
            created_at=job.created_at,
            updated_at=job.updated_at,
            result=result,
            error=error,
        )


def _identify_result_to_payload(result: IdentifyResult) -> dict:
    return IdentifyResponse(
        candidates=[
            IdentifyCandidateResponse(
                discogs_release_id=candidate.discogs_release_id,
                release_id=candidate.release_id,
                artist=candidate.artist,
                title=candidate.title,
                year=candidate.year,
                label=candidate.label,
                catalog_number=candidate.catalog_number,
                barcode=candidate.barcode,
                cover_image_url=candidate.cover_image_url,
                match_source=candidate.match_source,
                matched_on=list(candidate.matched_on),
                confidence=candidate.confidence,
            )
            for candidate in result.candidates
        ]
    ).model_dump(mode="json")


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def _map_exception_to_failure(error: Exception, status: str | None) -> IdentifyJobFailure:
    if isinstance(error, IdentifyValidationError):
        return IdentifyJobFailure(code=error.code, message=error.message, failed_step="upload")
    if isinstance(error, DiscogsClientError):
        return IdentifyJobFailure(
            code="discogs_unavailable",
            message="Discogs is unavailable. Retry in a moment.",
            failed_step="search",
        )
    if status == IdentifyJobStatus.PREPROCESSING_IMAGE.value:
        return IdentifyJobFailure(
            code="image_preprocessing_failed",
            message="Image preparation failed. Retry with another photo.",
            failed_step="extract",
        )
    if status == IdentifyJobStatus.EXTRACTING_TEXT.value:
        return IdentifyJobFailure(
            code="ocr_failed",
            message="Text extraction failed. Retry with another photo.",
            failed_step="extract",
        )
    if status == IdentifyJobStatus.PARSING_IDENTIFIERS.value:
        return IdentifyJobFailure(
            code="identifier_parse_failed",
            message="Could not read enough label details. Retry with another photo.",
            failed_step="extract",
        )
    if status in {
        IdentifyJobStatus.SEARCHING_LOCAL.value,
        IdentifyJobStatus.SEARCHING_DISCOGS.value,
        IdentifyJobStatus.RANKING_CANDIDATES.value,
    }:
        return IdentifyJobFailure(
            code="candidate_search_failed",
            message="Candidate search failed. Retry in a moment.",
            failed_step="search",
        )
    return IdentifyJobFailure(
        code="identify_failed",
        message="Identify processing failed. Retry or use Manual Search.",
        failed_step="unknown",
    )
