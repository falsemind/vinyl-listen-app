import logging
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.config import settings
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
from app.services.identify_service import (
    IdentifyCanceledError,
    IdentifyResult,
    IdentifyService,
    IdentifyValidationError,
)

logger = logging.getLogger(__name__)

DEFAULT_IDENTIFY_JOB_TTL = timedelta(hours=24)
IDENTIFY_CAPACITY_EXCEEDED_CODE = "identify_capacity_exceeded"
IDENTIFY_CAPACITY_EXCEEDED_MESSAGE = "Identify capacity is full. Please retry later."
ACTIVE_IDENTIFY_JOB_STATUSES = {
    IdentifyJobStatus.QUEUED.value,
    IdentifyJobStatus.UPLOAD_RECEIVED.value,
    IdentifyJobStatus.PREPROCESSING_IMAGE.value,
    IdentifyJobStatus.EXTRACTING_TEXT.value,
    IdentifyJobStatus.PARSING_IDENTIFIERS.value,
    IdentifyJobStatus.SEARCHING_LOCAL.value,
    IdentifyJobStatus.SEARCHING_DISCOGS.value,
    IdentifyJobStatus.RANKING_CANDIDATES.value,
}


class IdentifyJobNotFoundError(Exception):
    pass


class IdentifyJobExpiredError(Exception):
    pass


class IdentifyCapacityExceededError(Exception):
    status_code = 429
    code = IDENTIFY_CAPACITY_EXCEEDED_CODE
    message = IDENTIFY_CAPACITY_EXCEEDED_MESSAGE


class IdentifyAdmissionTicket:
    def __init__(self, controller: "IdentifyAdmissionController") -> None:
        self._controller = controller
        self._released = False
        self._lock = threading.Lock()

    def release(self) -> None:
        with self._lock:
            if self._released:
                return
            self._released = True
            self._controller.release()


class IdentifyAdmissionController:
    def __init__(self, *, max_concurrent_jobs: int, client_lock_stripes: int = 64) -> None:
        if max_concurrent_jobs <= 0:
            raise ValueError("max_concurrent_jobs must be positive.")
        if client_lock_stripes <= 0:
            raise ValueError("client_lock_stripes must be positive.")
        self._semaphore = threading.BoundedSemaphore(max_concurrent_jobs)
        self._admission_lock = threading.Lock()
        self._client_locks = tuple(threading.Lock() for _ in range(client_lock_stripes))

    def acquire_global_slot(self) -> IdentifyAdmissionTicket:
        if not self._semaphore.acquire(blocking=False):
            raise IdentifyCapacityExceededError
        return IdentifyAdmissionTicket(self)

    def release(self) -> None:
        self._semaphore.release()

    @contextmanager
    def client_admission_lock(self, client_key: str) -> Iterator[None]:
        lock = self._client_locks[hash(client_key) % len(self._client_locks)]
        lock.acquire()
        try:
            yield
        finally:
            lock.release()

    @contextmanager
    def db_admission_lock(self, client_key: str) -> Iterator[None]:
        with self._admission_lock, self.client_admission_lock(client_key):
            yield


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


@dataclass(frozen=True)
class IdentifyJobCancellationToken:
    db: Session
    job_id: str
    repository: IdentifyJobRepository

    def is_cancel_requested(self) -> bool:
        return self.repository.is_cancel_requested(self.db, self.job_id)


class IdentifyJobService:
    def __init__(
        self,
        *,
        identify_service: IdentifyService | None = None,
        repository: IdentifyJobRepository | None = None,
        admission_controller: IdentifyAdmissionController | None = None,
        session_factory: Callable[[], Session] = SessionLocal,
        now_provider: Callable[[], datetime] | None = None,
        job_ttl: timedelta = DEFAULT_IDENTIFY_JOB_TTL,
        max_active_jobs_per_client: int = settings.identify_max_active_jobs_per_client,
        max_active_jobs_global: int = settings.identify_max_active_jobs_global,
        stale_active_job_timeout: timedelta = timedelta(seconds=settings.identify_stale_active_job_timeout_seconds),
    ) -> None:
        self._identify_service = identify_service or IdentifyService()
        self._repository = repository or IdentifyJobRepository()
        self._admission_controller = admission_controller or IdentifyAdmissionController(
            max_concurrent_jobs=settings.identify_max_concurrent_jobs,
        )
        self._session_factory = session_factory
        self._now_provider = now_provider or (lambda: datetime.now(UTC))
        self._service_started_at = self._now_provider()
        self._job_ttl = job_ttl
        self._max_active_jobs_per_client = max_active_jobs_per_client
        self._max_active_jobs_global = max_active_jobs_global
        self._stale_active_job_timeout = stale_active_job_timeout
        self._admission_tickets: dict[str, IdentifyAdmissionTicket] = {}
        self._admission_tickets_lock = threading.Lock()

    def create_job(
        self,
        db: Session,
        *,
        image_bytes: bytes,
        filename: str,
        content_type: str,
        client_key: str = "unknown",
    ) -> IdentifyJobStatusResponse:
        self._identify_service.validate_upload(
            image_bytes=image_bytes,
            filename=filename,
            content_type=content_type,
        )
        now = self._now_provider()
        with self._admission_controller.db_admission_lock(client_key):
            self._expire_stale_active_jobs(db, now=now)

            active_job_count = self._repository.count_active_by_client(
                db,
                client_key=client_key,
                active_statuses=ACTIVE_IDENTIFY_JOB_STATUSES,
            )
            if active_job_count >= self._max_active_jobs_per_client:
                logger.info(
                    "Identify admission rejected reason=client_active_limit client_active_jobs=%s "
                    "max_active_jobs_per_client=%s code=%s retry_after_seconds=%s",
                    active_job_count,
                    self._max_active_jobs_per_client,
                    IDENTIFY_CAPACITY_EXCEEDED_CODE,
                    settings.identify_capacity_retry_after_seconds,
                )
                raise IdentifyCapacityExceededError

            if self._max_active_jobs_global > 0:
                active_global_job_count = self._repository.count_active(
                    db,
                    active_statuses=ACTIVE_IDENTIFY_JOB_STATUSES,
                )
                if active_global_job_count >= self._max_active_jobs_global:
                    logger.info(
                        "Identify admission rejected reason=global_active_limit active_jobs=%s "
                        "max_active_jobs_global=%s code=%s retry_after_seconds=%s",
                        active_global_job_count,
                        self._max_active_jobs_global,
                        IDENTIFY_CAPACITY_EXCEEDED_CODE,
                        settings.identify_capacity_retry_after_seconds,
                    )
                    raise IdentifyCapacityExceededError

            admission_ticket = self._admission_controller.acquire_global_slot()
            job_id = str(uuid4())
            try:
                job = self._repository.create(
                    db,
                    job_id=job_id,
                    status=IdentifyJobStatus.UPLOAD_RECEIVED.value,
                    message="Image upload received",
                    client_key=client_key,
                    filename=filename,
                    content_type=content_type,
                    created_at=now,
                    expires_at=now + self._job_ttl,
                )
            except Exception:
                admission_ticket.release()
                raise
            with self._admission_tickets_lock:
                self._admission_tickets[job_id] = admission_ticket
            logger.info(
                "Identify admission allowed job_id=%s client_active_jobs=%s max_active_jobs_per_client=%s",
                job_id,
                active_job_count + 1,
                self._max_active_jobs_per_client,
            )
            return self._to_response(job)

    def get_job(self, db: Session, job_id: str) -> IdentifyJobStatusResponse:
        job = self._repository.get(db, job_id)
        if job is None:
            raise IdentifyJobNotFoundError(job_id)
        if _ensure_utc(job.expires_at) <= self._now_provider():
            raise IdentifyJobExpiredError(job_id)
        return self._to_response(job)

    def cancel_job(self, db: Session, job_id: str) -> IdentifyJobStatusResponse:
        job = self._repository.request_cancel(db, job_id, requested_at=self._now_provider())
        if job is None:
            raise IdentifyJobNotFoundError(job_id)
        logger.info(
            "Identify job cancellation requested job_id=%s status=%s cancel_requested=%s",
            job_id,
            job.status,
            job.cancel_requested_at is not None,
        )
        return self._to_response(job)

    def process_job(self, job_id: str, *, image_bytes: bytes, filename: str, content_type: str) -> None:
        started_at = time.monotonic()
        admission_ticket = self._pop_admission_ticket(job_id)
        try:
            with self._session_factory() as db:
                job = self._repository.get(db, job_id)
                if job is None:
                    logger.warning("Identify job disappeared before processing job_id=%s", job_id)
                    return
                logger.info("Identify job started job_id=%s status=%s", job_id, job.status)

                progress_reporter = DatabaseIdentifyProgressReporter(
                    db=db,
                    job=job,
                    repository=self._repository,
                    now_provider=self._now_provider,
                )
                cancellation_token = IdentifyJobCancellationToken(
                    db=db,
                    job_id=job_id,
                    repository=self._repository,
                )

                try:
                    result = self._identify_service.identify(
                        db,
                        image_bytes=image_bytes,
                        filename=filename,
                        content_type=content_type,
                        progress_reporter=progress_reporter,
                        cancellation_checker=cancellation_token.is_cancel_requested,
                    )
                except IdentifyCanceledError:
                    job = self._repository.get(db, job_id)
                    if job is None:
                        logger.warning("Identify job disappeared before cancellation job_id=%s", job_id)
                        return
                    self._repository.mark_canceled(
                        db,
                        job,
                        message="Identify canceled",
                        updated_at=self._now_provider(),
                    )
                    logger.info(
                        "Identify job canceled job_id=%s duration_seconds=%.3f",
                        job_id,
                        time.monotonic() - started_at,
                    )
                    return
                except Exception as error:  # noqa: BLE001
                    job = self._repository.get(db, job_id)
                    failure = _map_exception_to_failure(error, job.status if job else None)
                    logger.exception(
                        "Identify job failed job_id=%s code=%s duration_seconds=%.3f",
                        job_id,
                        failure.code,
                        time.monotonic() - started_at,
                    )
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
                if cancellation_token.is_cancel_requested():
                    self._repository.mark_canceled(
                        db,
                        job,
                        message="Identify canceled",
                        updated_at=self._now_provider(),
                    )
                    logger.info(
                        "Identify job canceled before completion job_id=%s duration_seconds=%.3f",
                        job_id,
                        time.monotonic() - started_at,
                    )
                    return
                self._repository.complete(
                    db,
                    job,
                    result=_identify_result_to_payload(result),
                    message="Identify completed",
                    updated_at=self._now_provider(),
                )
                logger.info(
                    "Identify job completed job_id=%s duration_seconds=%.3f",
                    job_id,
                    time.monotonic() - started_at,
                )
        finally:
            if admission_ticket is not None:
                admission_ticket.release()

    def acquire_sync_identify_slot(self) -> IdentifyAdmissionTicket:
        try:
            ticket = self._admission_controller.acquire_global_slot()
        except IdentifyCapacityExceededError:
            logger.info(
                "Identify admission rejected reason=sync_global_slot code=%s retry_after_seconds=%s",
                IDENTIFY_CAPACITY_EXCEEDED_CODE,
                settings.identify_capacity_retry_after_seconds,
            )
            raise
        logger.debug("Identify admission allowed mode=sync")
        return ticket

    def _pop_admission_ticket(self, job_id: str) -> IdentifyAdmissionTicket | None:
        with self._admission_tickets_lock:
            return self._admission_tickets.pop(job_id, None)

    def _expire_stale_active_jobs(self, db: Session, *, now: datetime) -> int:
        if self._stale_active_job_timeout.total_seconds() <= 0:
            return 0

        stale_before = max(
            now - self._stale_active_job_timeout,
            self._service_started_at - timedelta(microseconds=1),
        )
        return self._repository.expire_stale_active(
            db,
            active_statuses=ACTIVE_IDENTIFY_JOB_STATUSES,
            stale_before=stale_before,
            expires_at_or_before=now,
            updated_at=now,
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
            cancel_requested=job.cancel_requested_at is not None,
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
                format=candidate.format,
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
