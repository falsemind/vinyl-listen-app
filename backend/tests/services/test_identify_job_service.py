import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.identify_job import IdentifyJob
from app.pipelines.identification import IdentifyCandidate
from app.services.discogs_service import DiscogsClientError
from app.services.identify_job_service import (
    IdentifyAdmissionController,
    IdentifyCapacityExceededError,
    IdentifyJobNotFoundError,
    IdentifyJobService,
)
from app.services.identify_service import IdentifyResult, IdentifyValidationError


class SuccessfulIdentifyService:
    def validate_upload(self, *, image_bytes: bytes, filename: str, content_type: str) -> None:
        _ = (image_bytes, filename, content_type)

    def identify(self, _db, *, image_bytes: bytes, filename: str, content_type: str, progress_reporter=None):
        _ = (image_bytes, filename, content_type)
        if progress_reporter is not None:
            progress_reporter.update("searching_local", "Searching local releases")
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

    def identify(self, _db, *, image_bytes: bytes, filename: str, content_type: str, progress_reporter=None):
        _ = (image_bytes, filename, content_type, progress_reporter)
        raise self._error


class ProgressFailingIdentifyService(SuccessfulIdentifyService):
    def identify(self, _db, *, image_bytes: bytes, filename: str, content_type: str, progress_reporter=None):
        _ = (image_bytes, filename, content_type)
        if progress_reporter is not None:
            progress_reporter.update("extracting_text", "Extracting text from image")
        raise RuntimeError("OCR failed")


def test_identify_job_service_completes_job() -> None:
    session_factory = _build_session_factory()
    service = IdentifyJobService(
        identify_service=SuccessfulIdentifyService(),
        session_factory=session_factory,
        now_provider=lambda: datetime(2026, 5, 12, 10, 0, 0, tzinfo=UTC),
    )

    with session_factory() as db:
        job = service.create_job(db, image_bytes=b"image", filename="cover.jpg", content_type="image/jpeg")

    service.process_job(job.job_id, image_bytes=b"image", filename="cover.jpg", content_type="image/jpeg")

    with session_factory() as db:
        completed = service.get_job(db, job.job_id)

    assert completed.status == "completed"
    assert completed.result is not None
    assert completed.result.candidates[0].discogs_release_id == 123
    assert completed.error is None


def test_identify_job_service_persists_discogs_failure() -> None:
    session_factory = _build_session_factory()
    service = IdentifyJobService(
        identify_service=FailingIdentifyService(DiscogsClientError("down")),
        session_factory=session_factory,
        now_provider=lambda: datetime(2026, 5, 12, 10, 0, 0, tzinfo=UTC),
    )

    with session_factory() as db:
        job = service.create_job(db, image_bytes=b"image", filename="cover.jpg", content_type="image/jpeg")

    service.process_job(job.job_id, image_bytes=b"image", filename="cover.jpg", content_type="image/jpeg")

    with session_factory() as db:
        failed = service.get_job(db, job.job_id)

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
        job = service.create_job(db, image_bytes=b"image", filename="cover.jpg", content_type="image/jpeg")

    service.process_job(job.job_id, image_bytes=b"image", filename="cover.jpg", content_type="image/jpeg")

    with session_factory() as db:
        failed = service.get_job(db, job.job_id)

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
            service.create_job(db, image_bytes=b"", filename="cover.jpg", content_type="image/jpeg")
        except IdentifyValidationError as raised:
            assert raised.code == "empty_image"
        else:
            raise AssertionError("Expected IdentifyValidationError")
        assert db.query(IdentifyJob).count() == 0


def test_identify_job_service_rejects_per_client_active_job_over_capacity() -> None:
    session_factory = _build_session_factory()
    service = IdentifyJobService(
        identify_service=SuccessfulIdentifyService(),
        admission_controller=IdentifyAdmissionController(max_concurrent_jobs=2),
        session_factory=session_factory,
        max_active_jobs_per_client=1,
    )

    with session_factory() as db:
        first_job = service.create_job(
            db,
            image_bytes=b"image",
            filename="cover.jpg",
            content_type="image/jpeg",
            client_key="client-a",
        )

        try:
            service.create_job(
                db,
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
            image_bytes=b"image",
            filename="cover.jpg",
            content_type="image/jpeg",
            client_key="client-a",
        )
        try:
            service.create_job(
                db,
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
            image_bytes=b"image",
            filename="cover.jpg",
            content_type="image/jpeg",
            client_key="client-a",
        )
        try:
            service.create_job(
                db,
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
            image_bytes=b"image",
            filename="cover.jpg",
            content_type="image/jpeg",
            client_key="client-a",
        )

    service.process_job(first_job.job_id, image_bytes=b"image", filename="cover.jpg", content_type="image/jpeg")

    with session_factory() as db:
        second_job = service.create_job(
            db,
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
        job = service.create_job(db, image_bytes=b"image", filename="cover.jpg", content_type="image/jpeg")
        canceled = service.cancel_job(db, job.job_id)

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

        canceled = service.cancel_job(db, "completed-job")

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
            service.cancel_job(db, "missing")
        except IdentifyJobNotFoundError:
            pass
        else:
            raise AssertionError("Expected IdentifyJobNotFoundError")


class FailingValidationIdentifyService(SuccessfulIdentifyService):
    def __init__(self, error: IdentifyValidationError) -> None:
        self._error = error

    def validate_upload(self, *, image_bytes: bytes, filename: str, content_type: str) -> None:
        _ = (image_bytes, filename, content_type)
        raise self._error


def _build_session_factory():
    engine = create_engine("sqlite:///:memory:")
    IdentifyJob.__table__.create(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


def _build_threadsafe_session_factory():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    IdentifyJob.__table__.create(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)
