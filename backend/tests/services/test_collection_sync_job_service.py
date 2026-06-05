from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.collection_sync_job import CollectionSyncJob
from app.services.collection_sync_job_service import CollectionSyncJobService
from app.services.collection_sync_service import CollectionSyncError, CollectionSyncResult


class SuccessfulCollectionSyncService:
    def sync_collection(self, _db, *, progress_reporter=None) -> CollectionSyncResult:
        if progress_reporter is not None:
            progress_reporter(step="fetching", message="Fetching collection data")
            progress_reporter(step="importing", message="Importing data", total_items=3, processed_items=1)
            progress_reporter(
                step="finalizing",
                message="Finalizing collection sync",
                total_items=3,
                processed_items=2,
            )

        return CollectionSyncResult(
            total_items=3,
            unique_releases=2,
            added_count=1,
            updated_count=1,
            removed_count=1,
        )


class FailingCollectionSyncService:
    def sync_collection(self, _db, *, progress_reporter=None) -> CollectionSyncResult:
        if progress_reporter is not None:
            progress_reporter(step="fetching", message="Fetching collection data")
        raise CollectionSyncError("Collection item is missing metadata.")


def test_collection_sync_job_service_completes_job() -> None:
    SessionFactory = _build_session_factory()
    now = datetime(2026, 6, 4, 12, 0, tzinfo=UTC)
    service = CollectionSyncJobService(
        sync_service=SuccessfulCollectionSyncService(),
        session_factory=SessionFactory,
        now_provider=lambda: now,
        require_discogs_config=False,
    )

    with SessionFactory() as db:
        job = service.create_job(db)

    service.process_job(job.job_id)

    with SessionFactory() as db:
        completed = service.get_job(db, job.job_id)

    assert completed.status == "succeeded"
    assert completed.step == "loading"
    assert completed.message == "Collection sync complete"
    assert completed.total_items == 3
    assert completed.processed_items == 2
    assert completed.added_count == 1
    assert completed.updated_count == 1
    assert completed.removed_count == 1
    assert completed.error is None


def test_collection_sync_job_service_persists_sync_failure() -> None:
    SessionFactory = _build_session_factory()
    now = datetime(2026, 6, 4, 12, 0, tzinfo=UTC)
    service = CollectionSyncJobService(
        sync_service=FailingCollectionSyncService(),
        session_factory=SessionFactory,
        now_provider=lambda: now,
        require_discogs_config=False,
    )

    with SessionFactory() as db:
        job = service.create_job(db)

    service.process_job(job.job_id)

    with SessionFactory() as db:
        failed = service.get_job(db, job.job_id)

    assert failed.status == "failed"
    assert failed.error is not None
    assert failed.error.code == "collection_sync_failed"
    assert failed.error.failed_step == "importing"
    assert failed.message == "Collection item is missing metadata."


def test_collection_sync_job_service_expires_orphaned_active_job_after_restart() -> None:
    SessionFactory = _build_session_factory()
    previous_process_time = datetime(2026, 6, 4, 12, 0, tzinfo=UTC)
    restarted_process_time = datetime(2026, 6, 4, 12, 1, tzinfo=UTC)
    service = CollectionSyncJobService(
        sync_service=SuccessfulCollectionSyncService(),
        session_factory=SessionFactory,
        now_provider=lambda: restarted_process_time,
        require_discogs_config=False,
    )

    with SessionFactory() as db:
        db.add(
            CollectionSyncJob(
                id="orphaned-job",
                status="running",
                step="fetching",
                message="Fetching collection data",
                created_at=previous_process_time,
                updated_at=previous_process_time,
                expires_at=previous_process_time + timedelta(hours=1),
            )
        )
        db.commit()

        active_job = service.get_active_job(db)
        stale_job = db.get(CollectionSyncJob, "orphaned-job")

    assert active_job is None
    assert stale_job is not None
    assert stale_job.status == "expired"
    assert stale_job.error is not None
    assert stale_job.error["code"] == "collection_sync_job_stale"


def test_collection_sync_job_service_returns_expired_when_polling_orphaned_job() -> None:
    SessionFactory = _build_session_factory()
    previous_process_time = datetime(2026, 6, 4, 12, 0, tzinfo=UTC)
    restarted_process_time = datetime(2026, 6, 4, 12, 1, tzinfo=UTC)
    service = CollectionSyncJobService(
        sync_service=SuccessfulCollectionSyncService(),
        session_factory=SessionFactory,
        now_provider=lambda: restarted_process_time,
        require_discogs_config=False,
    )

    with SessionFactory() as db:
        db.add(
            CollectionSyncJob(
                id="orphaned-job",
                status="running",
                step="fetching",
                message="Fetching collection data",
                created_at=previous_process_time,
                updated_at=previous_process_time,
                expires_at=previous_process_time + timedelta(hours=1),
            )
        )
        db.commit()

        expired_job = service.get_job(db, "orphaned-job")

    assert expired_job.status == "expired"
    assert expired_job.error is not None
    assert expired_job.error.code == "collection_sync_job_stale"
    assert expired_job.error.failed_step == "fetching"


def _build_session_factory():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    CollectionSyncJob.__table__.create(engine)
    return sessionmaker(bind=engine)
