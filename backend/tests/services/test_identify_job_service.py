import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.auth import UsageEvent, UserAccount, UserEntitlement
from app.models.identify_job import IdentifyJob
from app.pipelines.identification import IdentifyCandidate
from app.repositories.identify_job_repository import IdentifyJobRepository
from app.services.discogs_service import DiscogsClientError
from app.services.identify_job_service import (
    IdentifyAdmissionController,
    IdentifyCapacityExceededError,
    IdentifyJobNotFoundError,
    IdentifyJobService,
)
from app.services.identify_service import IdentifyCanceledError, IdentifyResult, IdentifyValidationError


class SuccessfulIdentifyService:
    def validate_upload(self, *, image_bytes: bytes, filename: str, content_type: str) -> None:
        _ = (image_bytes, filename, content_type)

    def identify(
        self,
        _db,
        *,
        image_bytes: bytes,
        filename: str,
        content_type: str,
        user_id: str | None = None,
        progress_reporter=None,
        cancellation_checker=None,
    ):
        _ = (image_bytes, filename, content_type)
        self.user_ids = getattr(self, "user_ids", [])
        self.user_ids.append(user_id)
        if cancellation_checker is not None and cancellation_checker():
            raise IdentifyCanceledError
        if progress_reporter is not None:
            progress_reporter.update("searching_local", "Searching local releases")
        if cancellation_checker is not None and cancellation_checker():
            raise IdentifyCanceledError
        return IdentifyResult(
            candidates=(
                IdentifyCandidate(
                    discogs_release_id=123,
                    release_id="release-123",
                    artist="Artist",
                    title="Title",
                    year=2026,
                    label="Label",
                    catalog_number="CAT-1",
                    barcode=None,
                    cover_image_url=None,
                    match_source="local",
                    matched_on=("local_lookup",),
                    confidence=0.9,
                ),
            )
        )


class FailingIdentifyService(SuccessfulIdentifyService):
    def __init__(self, error: Exception) -> None:
        self._error = error

    def identify(
        self,
        _db,
        *,
        image_bytes: bytes,
        filename: str,
        content_type: str,
        user_id: str | None = None,
        progress_reporter=None,
        cancellation_checker=None,
    ):
        _ = (image_bytes, filename, content_type, user_id, progress_reporter, cancellation_checker)
        raise self._error


class ProgressFailingIdentifyService(SuccessfulIdentifyService):
    def identify(
        self,
        _db,
        *,
        image_bytes: bytes,
        filename: str,
        content_type: str,
        user_id: str | None = None,
        progress_reporter=None,
        cancellation_checker=None,
    ):
        _ = (image_bytes, filename, content_type, user_id, cancellation_checker)
        if progress_reporter is not None:
            progress_reporter.update("extracting_text", "Extracting text from image")
        raise RuntimeError("OCR failed")


class MidPipelineCancelingIdentifyService(SuccessfulIdentifyService):
    def __init__(self, requested_at: datetime) -> None:
        self._requested_at = requested_at

    def identify(
        self,
        db,
        *,
        image_bytes: bytes,
        filename: str,
        content_type: str,
        user_id: str | None = None,
        progress_reporter=None,
        cancellation_checker=None,
    ):
        _ = (image_bytes, filename, content_type, user_id)
        if progress_reporter is not None:
            progress_reporter.update("extracting_text", "Extracting text from image")
        job_id = db.query(IdentifyJob.id).one()[0]
        IdentifyJobRepository.request_cancel(db, job_id, requested_at=self._requested_at)
        if cancellation_checker is not None and cancellation_checker():
            raise IdentifyCanceledError
        raise AssertionError("Expected cancellation checker to stop processing")


class CompletionCancelingIdentifyService(SuccessfulIdentifyService):
    def __init__(self, requested_at: datetime) -> None:
        self._requested_at = requested_at

    def identify(
        self,
        db,
        *,
        image_bytes: bytes,
        filename: str,
        content_type: str,
        user_id: str | None = None,
        progress_reporter=None,
        cancellation_checker=None,
    ):
        _ = (image_bytes, filename, content_type, user_id, progress_reporter, cancellation_checker)
        job_id = db.query(IdentifyJob.id).one()[0]
        IdentifyJobRepository.request_cancel(db, job_id, requested_at=self._requested_at)
        return IdentifyResult(
            candidates=(
                IdentifyCandidate(
                    discogs_release_id=123,
                    release_id="release-123",
                    artist="Artist",
                    title="Title",
                    year=2026,
                    label="Label",
                    catalog_number="CAT-1",
                    barcode=None,
                    cover_image_url=None,
                    match_source="local",
                    matched_on=("local_lookup",),
                    confidence=0.9,
                ),
            )
        )


class StubEntitlementService:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def consume_usage(
        self,
        _db,
        *,
        user_id: str,
        capability: str,
        units: int = 1,
        event_metadata: dict | None = None,
    ) -> None:
        self.calls.append(
            {
                "user_id": user_id,
                "capability": capability,
                "units": units,
                "event_metadata": event_metadata,
            }
        )


def test_identify_job_service_completes_job() -> None:
    session_factory = _build_session_factory()
    identify_service = SuccessfulIdentifyService()
    service = IdentifyJobService(
        identify_service=identify_service,
        session_factory=session_factory,
        now_provider=lambda: datetime(2026, 5, 12, 10, 0, 0, tzinfo=UTC),
    )

    with session_factory() as db:
        job = service.create_job(
            db, user_id="user-a", image_bytes=b"image", filename="cover.jpg", content_type="image/jpeg"
        )

    service.process_job(job.job_id, image_bytes=b"image", filename="cover.jpg", content_type="image/jpeg")

    with session_factory() as db:
        completed = service.get_job(db, job.job_id, user_id="user-a")

    assert completed.status == "completed"
    assert completed.result is not None
    assert completed.result.candidates[0].discogs_release_id == 123
    assert completed.error is None
    assert identify_service.user_ids == ["user-a"]


def test_identify_job_service_persists_discogs_failure() -> None:
    session_factory = _build_session_factory()
    service = IdentifyJobService(
        identify_service=FailingIdentifyService(DiscogsClientError("down")),
        session_factory=session_factory,
        now_provider=lambda: datetime(2026, 5, 12, 10, 0, 0, tzinfo=UTC),
    )

    with session_factory() as db:
        job = service.create_job(
            db, user_id="user-a", image_bytes=b"image", filename="cover.jpg", content_type="image/jpeg"
        )

    service.process_job(job.job_id, image_bytes=b"image", filename="cover.jpg", content_type="image/jpeg")

    with session_factory() as db:
        failed = service.get_job(db, job.job_id, user_id="user-a")

    assert failed.status == "failed"
    assert failed.error is not None
    assert failed.error.code == "discogs_unavailable"
    assert failed.error.failed_step == "search"


def test_identify_job_service_maps_failure_from_last_progress_status() -> None:
    session_factory = _build_session_factory()
    service = IdentifyJobService(
        identify_service=ProgressFailingIdentifyService(),
        session_factory=session_factory,
        now_provider=lambda: datetime(2026, 5, 12, 10, 0, 0, tzinfo=UTC),
    )

    with session_factory() as db:
        job = service.create_job(
            db, user_id="user-a", image_bytes=b"image", filename="cover.jpg", content_type="image/jpeg"
        )

    service.process_job(job.job_id, image_bytes=b"image", filename="cover.jpg", content_type="image/jpeg")

    with session_factory() as db:
        failed = service.get_job(db, job.job_id, user_id="user-a")

    assert failed.status == "failed"
    assert failed.error is not None
    assert failed.error.code == "ocr_failed"
    assert failed.error.failed_step == "extract"


def test_identify_job_service_rejects_invalid_upload_before_job_creation() -> None:
    session_factory = _build_session_factory()
    error = IdentifyValidationError(message="Uploaded image is empty.", status_code=422, code="empty_image")
    service = IdentifyJobService(
        identify_service=FailingValidationIdentifyService(error),
        session_factory=session_factory,
    )

    with session_factory() as db:
        try:
            service.create_job(db, user_id="user-a", image_bytes=b"", filename="cover.jpg", content_type="image/jpeg")
        except IdentifyValidationError as raised:
            assert raised.code == "empty_image"
        else:
            raise AssertionError("Expected IdentifyValidationError")
        assert db.query(IdentifyJob).count() == 0


def test_identify_job_service_rejects_per_client_active_job_over_capacity() -> None:
    session_factory = _build_session_factory()
    entitlement_service = StubEntitlementService()
    service = IdentifyJobService(
        identify_service=SuccessfulIdentifyService(),
        entitlement_service=entitlement_service,
        admission_controller=IdentifyAdmissionController(max_concurrent_jobs=2),
        session_factory=session_factory,
        max_active_jobs_per_client=1,
    )

    with session_factory() as db:
        first_job = service.create_job(
            db,
            user_id="user-a",
            image_bytes=b"image",
            filename="cover.jpg",
            content_type="image/jpeg",
            client_key="client-a",
        )

        try:
            service.create_job(
                db,
                user_id="user-a",
                image_bytes=b"image",
                filename="cover.jpg",
                content_type="image/jpeg",
                client_key="client-a",
            )
        except IdentifyCapacityExceededError as error:
            assert error.code == "identify_capacity_exceeded"
        else:
            raise AssertionError("Expected IdentifyCapacityExceededError")

    service.process_job(first_job.job_id, image_bytes=b"image", filename="cover.jpg", content_type="image/jpeg")
    assert entitlement_service.calls == [
        {
            "user_id": "user-a",
            "capability": "ocr_identify",
            "units": 1,
            "event_metadata": {"source": "async_identify"},
        }
    ]


def test_identify_job_service_records_usage_after_admission() -> None:
    session_factory = _build_session_factory()
    entitlement_service = StubEntitlementService()
    service = IdentifyJobService(
        identify_service=SuccessfulIdentifyService(),
        entitlement_service=entitlement_service,
        session_factory=session_factory,
    )

    with session_factory() as db:
        service.create_job(
            db,
            user_id="user-a",
            image_bytes=b"image",
            filename="cover.jpg",
            content_type="image/jpeg",
            client_key="client-a",
        )

    assert entitlement_service.calls == [
        {
            "user_id": "user-a",
            "capability": "ocr_identify",
            "units": 1,
            "event_metadata": {"source": "async_identify"},
        }
    ]


def test_identify_job_service_creates_text_job_contract() -> None:
    session_factory = _build_session_factory()
    entitlement_service = StubEntitlementService()
    service = IdentifyJobService(
        identify_service=SuccessfulIdentifyService(),
        entitlement_service=entitlement_service,
        session_factory=session_factory,
    )

    with session_factory() as db:
        job = service.create_text_job(
            db,
            user_id="user-a",
            text_lines=["CAT No: SW038"],
            client_key="client-a",
        )

    assert job.status == "text_received"
    assert job.message == "Text input received"
    assert entitlement_service.calls == [
        {
            "user_id": "user-a",
            "capability": "ocr_identify",
            "units": 1,
            "event_metadata": {"source": "text_identify"},
        }
    ]


def test_identify_job_service_processes_text_job_contract_as_placeholder_failure() -> None:
    session_factory = _build_session_factory()
    service = IdentifyJobService(
        identify_service=SuccessfulIdentifyService(),
        session_factory=session_factory,
    )

    with session_factory() as db:
        job = service.create_text_job(
            db,
            user_id="user-a",
            text_lines=["CAT No: SW038"],
            client_key="client-a",
        )

    service.process_text_job(job.job_id, text_lines=["CAT No: SW038"], selected_catalog_number="SW038")

    with session_factory() as db:
        failed = service.get_job(db, job.job_id, user_id="user-a")

    assert failed.status == "failed"
    assert failed.error is not None
    assert failed.error.code == "text_identify_not_implemented"
    assert failed.error.failed_step == "parse"


def test_identify_job_service_scopes_job_access_by_user() -> None:
    session_factory = _build_session_factory()
    service = IdentifyJobService(
        identify_service=SuccessfulIdentifyService(),
        session_factory=session_factory,
    )

    with session_factory() as db:
        job = service.create_job(
            db,
            user_id="user-a",
            image_bytes=b"image",
            filename="cover.jpg",
            content_type="image/jpeg",
        )

        try:
            service.get_job(db, job.job_id, user_id="user-b")
        except IdentifyJobNotFoundError:
            pass
        else:
            raise AssertionError("Expected IdentifyJobNotFoundError")

        try:
            service.cancel_job(db, job.job_id, user_id="user-b")
        except IdentifyJobNotFoundError:
            pass
        else:
            raise AssertionError("Expected IdentifyJobNotFoundError")


def test_identify_job_service_serializes_same_client_admission() -> None:
    session_factory = _build_threadsafe_session_factory()
    service = IdentifyJobService(
        identify_service=SuccessfulIdentifyService(),
        admission_controller=IdentifyAdmissionController(max_concurrent_jobs=2),
        session_factory=session_factory,
        max_active_jobs_per_client=1,
    )
    barrier = threading.Barrier(2)

    def create_job_for_same_client() -> str:
        barrier.wait()
        with session_factory() as db:
            try:
                job = service.create_job(
                    db,
                    user_id="user-a",
                    image_bytes=b"image",
                    filename="cover.jpg",
                    content_type="image/jpeg",
                    client_key="client-a",
                )
            except IdentifyCapacityExceededError:
                return "rejected"
            return job.job_id

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: create_job_for_same_client(), range(2)))

    assert results.count("rejected") == 1
    accepted_job_ids = [result for result in results if result != "rejected"]
    assert len(accepted_job_ids) == 1

    with session_factory() as db:
        assert db.query(IdentifyJob).count() == 1

    service.process_job(accepted_job_ids[0], image_bytes=b"image", filename="cover.jpg", content_type="image/jpeg")


def test_identify_job_service_serializes_db_global_admission() -> None:
    session_factory = _build_threadsafe_session_factory()
    service = IdentifyJobService(
        identify_service=SuccessfulIdentifyService(),
        admission_controller=IdentifyAdmissionController(max_concurrent_jobs=2),
        session_factory=session_factory,
        max_active_jobs_per_client=2,
        max_active_jobs_global=1,
    )
    barrier = threading.Barrier(2)

    def create_job_for_client(client_key: str) -> str:
        barrier.wait()
        with session_factory() as db:
            try:
                job = service.create_job(
                    db,
                    user_id="user-a",
                    image_bytes=b"image",
                    filename="cover.jpg",
                    content_type="image/jpeg",
                    client_key=client_key,
                )
            except IdentifyCapacityExceededError:
                return "rejected"
            return job.job_id

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(create_job_for_client, ("client-a", "client-b")))

    assert results.count("rejected") == 1
    accepted_job_ids = [result for result in results if result != "rejected"]
    assert len(accepted_job_ids) == 1

    with session_factory() as db:
        assert db.query(IdentifyJob).count() == 1

    service.process_job(accepted_job_ids[0], image_bytes=b"image", filename="cover.jpg", content_type="image/jpeg")


def test_identify_job_service_rejects_when_global_capacity_is_full() -> None:
    session_factory = _build_session_factory()
    service = IdentifyJobService(
        identify_service=SuccessfulIdentifyService(),
        admission_controller=IdentifyAdmissionController(max_concurrent_jobs=1),
        session_factory=session_factory,
        max_active_jobs_per_client=2,
    )

    with session_factory() as db:
        first_job = service.create_job(
            db,
            user_id="user-a",
            image_bytes=b"image",
            filename="cover.jpg",
            content_type="image/jpeg",
            client_key="client-a",
        )
        try:
            service.create_job(
                db,
                user_id="user-a",
                image_bytes=b"image",
                filename="cover.jpg",
                content_type="image/jpeg",
                client_key="client-b",
            )
        except IdentifyCapacityExceededError as error:
            assert error.code == "identify_capacity_exceeded"
        else:
            raise AssertionError("Expected IdentifyCapacityExceededError")

    service.process_job(first_job.job_id, image_bytes=b"image", filename="cover.jpg", content_type="image/jpeg")


def test_identify_job_service_rejects_when_db_global_active_capacity_is_full() -> None:
    session_factory = _build_session_factory()
    service = IdentifyJobService(
        identify_service=SuccessfulIdentifyService(),
        admission_controller=IdentifyAdmissionController(max_concurrent_jobs=2),
        session_factory=session_factory,
        max_active_jobs_per_client=2,
        max_active_jobs_global=1,
    )

    with session_factory() as db:
        first_job = service.create_job(
            db,
            user_id="user-a",
            image_bytes=b"image",
            filename="cover.jpg",
            content_type="image/jpeg",
            client_key="client-a",
        )
        try:
            service.create_job(
                db,
                user_id="user-a",
                image_bytes=b"image",
                filename="cover.jpg",
                content_type="image/jpeg",
                client_key="client-b",
            )
        except IdentifyCapacityExceededError as error:
            assert error.code == "identify_capacity_exceeded"
        else:
            raise AssertionError("Expected IdentifyCapacityExceededError")

    service.process_job(first_job.job_id, image_bytes=b"image", filename="cover.jpg", content_type="image/jpeg")


def test_identify_job_service_expires_stale_active_job_before_admission() -> None:
    session_factory = _build_session_factory()
    now = datetime(2026, 5, 15, 12, 0, 0, tzinfo=UTC)
    service = IdentifyJobService(
        identify_service=SuccessfulIdentifyService(),
        admission_controller=IdentifyAdmissionController(max_concurrent_jobs=1),
        session_factory=session_factory,
        now_provider=lambda: now,
        max_active_jobs_per_client=1,
        stale_active_job_timeout=timedelta(minutes=15),
    )

    with session_factory() as db:
        db.add(
            IdentifyJob(
                id="stale-job",
                user_id="user-a",
                status="upload_received",
                client_key="client-a",
                message="Image upload received",
                filename="cover.jpg",
                content_type="image/jpeg",
                created_at=now - timedelta(minutes=30),
                updated_at=now - timedelta(minutes=30),
                expires_at=now + timedelta(hours=1),
            )
        )
        db.commit()

        new_job = service.create_job(
            db,
            user_id="user-a",
            image_bytes=b"image",
            filename="cover.jpg",
            content_type="image/jpeg",
            client_key="client-a",
        )
        stale_job = db.get(IdentifyJob, "stale-job")

    assert new_job.status == "upload_received"
    assert stale_job is not None
    assert stale_job.status == "expired"
    assert stale_job.error is not None
    assert stale_job.error["code"] == "identify_job_stale"

    service.process_job(new_job.job_id, image_bytes=b"image", filename="cover.jpg", content_type="image/jpeg")


def test_identify_job_service_expires_orphaned_active_job_after_restart() -> None:
    session_factory = _build_session_factory()
    previous_process_time = datetime(2026, 5, 15, 12, 0, 0, tzinfo=UTC)
    restarted_process_time = datetime(2026, 5, 15, 12, 1, 0, tzinfo=UTC)
    service = IdentifyJobService(
        identify_service=SuccessfulIdentifyService(),
        admission_controller=IdentifyAdmissionController(max_concurrent_jobs=1),
        session_factory=session_factory,
        now_provider=lambda: restarted_process_time,
        max_active_jobs_per_client=1,
        stale_active_job_timeout=timedelta(minutes=15),
    )

    with session_factory() as db:
        db.add(
            IdentifyJob(
                id="orphaned-job",
                user_id="user-a",
                status="upload_received",
                client_key="client-a",
                message="Image upload received",
                filename="cover.jpg",
                content_type="image/jpeg",
                created_at=previous_process_time,
                updated_at=previous_process_time,
                expires_at=previous_process_time + timedelta(hours=1),
            )
        )
        db.commit()

        new_job = service.create_job(
            db,
            user_id="user-a",
            image_bytes=b"image",
            filename="cover.jpg",
            content_type="image/jpeg",
            client_key="client-a",
        )
        orphaned_job = db.get(IdentifyJob, "orphaned-job")

    assert new_job.status == "upload_received"
    assert orphaned_job is not None
    assert orphaned_job.status == "expired"
    assert orphaned_job.error is not None
    assert orphaned_job.error["code"] == "identify_job_stale"

    service.process_job(new_job.job_id, image_bytes=b"image", filename="cover.jpg", content_type="image/jpeg")


def test_identify_job_service_releases_capacity_after_worker_failure() -> None:
    session_factory = _build_session_factory()
    service = IdentifyJobService(
        identify_service=FailingIdentifyService(RuntimeError("boom")),
        admission_controller=IdentifyAdmissionController(max_concurrent_jobs=1),
        session_factory=session_factory,
        max_active_jobs_per_client=2,
    )

    with session_factory() as db:
        first_job = service.create_job(
            db,
            user_id="user-a",
            image_bytes=b"image",
            filename="cover.jpg",
            content_type="image/jpeg",
            client_key="client-a",
        )

    service.process_job(first_job.job_id, image_bytes=b"image", filename="cover.jpg", content_type="image/jpeg")

    with session_factory() as db:
        second_job = service.create_job(
            db,
            user_id="user-a",
            image_bytes=b"image",
            filename="cover.jpg",
            content_type="image/jpeg",
            client_key="client-b",
        )

    assert second_job.status == "upload_received"


def test_identify_job_service_cancel_job_requests_cancel_for_active_job() -> None:
    now = datetime(2026, 5, 12, 10, 0, 0, tzinfo=UTC)
    session_factory = _build_session_factory()
    service = IdentifyJobService(
        identify_service=SuccessfulIdentifyService(),
        session_factory=session_factory,
        now_provider=lambda: now,
    )

    with session_factory() as db:
        job = service.create_job(
            db, user_id="user-a", image_bytes=b"image", filename="cover.jpg", content_type="image/jpeg"
        )
        canceled = service.cancel_job(db, job.job_id, user_id="user-a")

    assert canceled.status == "upload_received"
    assert canceled.cancel_requested is True


def test_identify_job_service_cancel_job_returns_terminal_job_without_rewriting_status() -> None:
    now = datetime(2026, 5, 12, 10, 0, 0, tzinfo=UTC)
    session_factory = _build_session_factory()
    service = IdentifyJobService(
        identify_service=SuccessfulIdentifyService(),
        session_factory=session_factory,
        now_provider=lambda: now,
    )

    with session_factory() as db:
        db.add(
            IdentifyJob(
                id="completed-job",
                user_id="user-a",
                status="completed",
                client_key="client-a",
                message="Identify completed",
                filename="cover.jpg",
                content_type="image/jpeg",
                created_at=now,
                updated_at=now,
                expires_at=now + timedelta(hours=1),
            )
        )
        db.commit()

        canceled = service.cancel_job(db, "completed-job", user_id="user-a")

    assert canceled.status == "completed"
    assert canceled.cancel_requested is False


def test_identify_job_service_cancel_job_raises_not_found() -> None:
    session_factory = _build_session_factory()
    service = IdentifyJobService(
        identify_service=SuccessfulIdentifyService(),
        session_factory=session_factory,
    )

    with session_factory() as db:
        try:
            service.cancel_job(db, "missing", user_id="user-a")
        except IdentifyJobNotFoundError:
            pass
        else:
            raise AssertionError("Expected IdentifyJobNotFoundError")


def test_identify_job_service_marks_canceled_before_first_work() -> None:
    now = datetime(2026, 5, 12, 10, 0, 0, tzinfo=UTC)
    session_factory = _build_session_factory()
    service = IdentifyJobService(
        identify_service=SuccessfulIdentifyService(),
        session_factory=session_factory,
        now_provider=lambda: now,
    )

    with session_factory() as db:
        job = service.create_job(
            db, user_id="user-a", image_bytes=b"image", filename="cover.jpg", content_type="image/jpeg"
        )
        service.cancel_job(db, job.job_id, user_id="user-a")

    service.process_job(job.job_id, image_bytes=b"image", filename="cover.jpg", content_type="image/jpeg")

    with session_factory() as db:
        canceled = service.get_job(db, job.job_id, user_id="user-a")

    assert canceled.status == "canceled"
    assert canceled.message == "Identify canceled"
    assert canceled.cancel_requested is True
    assert canceled.error is None
    assert canceled.result is None


def test_identify_job_service_marks_canceled_mid_pipeline() -> None:
    now = datetime(2026, 5, 12, 10, 0, 0, tzinfo=UTC)
    session_factory = _build_session_factory()
    service = IdentifyJobService(
        identify_service=MidPipelineCancelingIdentifyService(requested_at=now),
        session_factory=session_factory,
        now_provider=lambda: now,
    )

    with session_factory() as db:
        job = service.create_job(
            db, user_id="user-a", image_bytes=b"image", filename="cover.jpg", content_type="image/jpeg"
        )

    service.process_job(job.job_id, image_bytes=b"image", filename="cover.jpg", content_type="image/jpeg")

    with session_factory() as db:
        canceled = service.get_job(db, job.job_id, user_id="user-a")

    assert canceled.status == "canceled"
    assert canceled.message == "Identify canceled"
    assert canceled.cancel_requested is True
    assert canceled.error is None
    assert canceled.result is None


def test_identify_job_service_discards_result_when_cancel_requested_before_completion() -> None:
    now = datetime(2026, 5, 12, 10, 0, 0, tzinfo=UTC)
    session_factory = _build_session_factory()
    service = IdentifyJobService(
        identify_service=CompletionCancelingIdentifyService(requested_at=now),
        session_factory=session_factory,
        now_provider=lambda: now,
    )

    with session_factory() as db:
        job = service.create_job(
            db, user_id="user-a", image_bytes=b"image", filename="cover.jpg", content_type="image/jpeg"
        )

    service.process_job(job.job_id, image_bytes=b"image", filename="cover.jpg", content_type="image/jpeg")

    with session_factory() as db:
        canceled = service.get_job(db, job.job_id, user_id="user-a")

    assert canceled.status == "canceled"
    assert canceled.message == "Identify canceled"
    assert canceled.cancel_requested is True
    assert canceled.error is None
    assert canceled.result is None


class FailingValidationIdentifyService(SuccessfulIdentifyService):
    def __init__(self, error: IdentifyValidationError) -> None:
        self._error = error

    def validate_upload(self, *, image_bytes: bytes, filename: str, content_type: str) -> None:
        _ = (image_bytes, filename, content_type)
        raise self._error


def _build_session_factory():
    engine = create_engine("sqlite:///:memory:")
    UserAccount.__table__.create(engine)
    UserEntitlement.__table__.create(engine)
    UsageEvent.__table__.create(engine)
    IdentifyJob.__table__.create(engine)
    _seed_users(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


def _build_threadsafe_session_factory():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    UserAccount.__table__.create(engine)
    UserEntitlement.__table__.create(engine)
    UsageEvent.__table__.create(engine)
    IdentifyJob.__table__.create(engine)
    _seed_users(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


def _seed_users(engine) -> None:
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    with session_factory() as db:
        db.add_all(
            [
                UserAccount(
                    id="user-a",
                    email="user-a@example.com",
                    password_hash="hash",
                    normalized_email="user-a@example.com",
                    password_hash_algorithm="argon2id",
                    email_verified_at=None,
                ),
                UserAccount(
                    id="user-b",
                    email="user-b@example.com",
                    password_hash="hash",
                    normalized_email="user-b@example.com",
                    password_hash_algorithm="argon2id",
                    email_verified_at=None,
                ),
            ]
        )
        db.commit()
