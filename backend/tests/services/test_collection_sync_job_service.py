from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.auth import UserAccount
from app.models.collection_sync_job import CollectionSyncJob
from app.schemas.collection import CollectionSourceOfTruth
from app.schemas.integrations import DiscogsIntegrationStatusResponse
from app.services.collection_sync_job_service import CollectionSyncConfigurationError, CollectionSyncJobService
from app.services.collection_sync_service import CollectionSyncError, CollectionSyncResult


class SuccessfulCollectionSyncService:
    def sync_collection(
        self,
        _db,
        *,
        user_id: str,
        progress_reporter=None,
        commit: bool = True,
    ) -> CollectionSyncResult:
        _ = user_id, commit
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
    def sync_collection(
        self,
        _db,
        *,
        user_id: str,
        progress_reporter=None,
        commit: bool = True,
    ) -> CollectionSyncResult:
        _ = user_id, commit
        if progress_reporter is not None:
            progress_reporter(step="fetching", message="Fetching collection data")
        raise CollectionSyncError("Collection item is missing metadata.")


class RecordingCollectionSyncService:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def sync_collection(
        self,
        _db,
        *,
        user_id: str,
        progress_reporter=None,
        commit: bool = True,
    ) -> CollectionSyncResult:
        self.calls.append({"user_id": user_id, "commit": commit, "progress_reporter": progress_reporter})
        return CollectionSyncResult(
            total_items=0,
            unique_releases=0,
            added_count=0,
            updated_count=0,
            removed_count=0,
        )


class FakeDiscogsIntegrationService:
    def __init__(self, *, access_token_saved: bool) -> None:
        self.access_token_saved = access_token_saved

    def get_status(self, _db, *, user_id: str | None = None) -> DiscogsIntegrationStatusResponse:
        _ = user_id
        return DiscogsIntegrationStatusResponse(
            access_token_saved=self.access_token_saved,
            source_of_truth=CollectionSourceOfTruth.APP,
            backend_identify_enabled=self.access_token_saved,
        )


def test_collection_sync_job_service_rejects_job_without_saved_discogs_token() -> None:
    SessionFactory = _build_session_factory()
    service = CollectionSyncJobService(
        sync_service=SuccessfulCollectionSyncService(),
        session_factory=SessionFactory,
        discogs_integration_service=FakeDiscogsIntegrationService(access_token_saved=False),
    )

    with SessionFactory() as db, pytest.raises(CollectionSyncConfigurationError):
        service.create_job(db, user_id="user-a")


def test_collection_sync_job_service_allows_job_with_saved_discogs_token() -> None:
    SessionFactory = _build_session_factory()
    now = datetime(2026, 6, 4, 12, 0, tzinfo=UTC)
    service = CollectionSyncJobService(
        sync_service=SuccessfulCollectionSyncService(),
        session_factory=SessionFactory,
        now_provider=lambda: now,
        discogs_integration_service=FakeDiscogsIntegrationService(access_token_saved=True),
    )

    with SessionFactory() as db:
        job = service.create_job(db, user_id="user-a")

    assert job.status == "queued"


def test_collection_sync_job_service_locks_account_data_for_create_and_process(monkeypatch) -> None:
    SessionFactory = _build_session_factory()
    now = datetime(2026, 6, 4, 12, 0, tzinfo=UTC)
    service = CollectionSyncJobService(
        sync_service=SuccessfulCollectionSyncService(),
        session_factory=SessionFactory,
        now_provider=lambda: now,
        require_discogs_config=False,
    )
    locked_user_ids: list[str] = []

    def record_account_data_lock(_db, *, user_id: str, repository=None) -> None:
        _ = repository
        locked_user_ids.append(user_id)

    monkeypatch.setattr(
        "app.services.collection_sync_job_service.lock_account_data_mutation",
        record_account_data_lock,
    )

    with SessionFactory() as db:
        job = service.create_job(db, user_id="user-a")

    service.process_job(job.job_id)

    assert locked_user_ids == ["user-a"] * 2


def test_collection_sync_job_service_skips_processing_when_reset_deletes_job_before_lock(monkeypatch) -> None:
    SessionFactory = _build_session_factory()
    now = datetime(2026, 6, 4, 12, 0, tzinfo=UTC)
    sync_service = RecordingCollectionSyncService()
    service = CollectionSyncJobService(
        sync_service=sync_service,
        session_factory=SessionFactory,
        now_provider=lambda: now,
        require_discogs_config=False,
    )

    with SessionFactory() as db:
        job = service.create_job(db, user_id="user-a")

    def delete_job_during_reset_lock(db, *, user_id: str, repository=None) -> None:
        _ = user_id, repository
        db.query(CollectionSyncJob).filter(CollectionSyncJob.id == job.job_id).delete()
        db.flush()

    monkeypatch.setattr(
        "app.services.collection_sync_job_service.lock_account_data_mutation",
        delete_job_during_reset_lock,
    )

    service.process_job(job.job_id)

    assert sync_service.calls == []


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
        job = service.create_job(db, user_id="user-a")

    service.process_job(job.job_id)

    with SessionFactory() as db:
        completed = service.get_job(db, job.job_id, user_id="user-a")

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
        job = service.create_job(db, user_id="user-a")

    service.process_job(job.job_id)

    with SessionFactory() as db:
        failed = service.get_job(db, job.job_id, user_id="user-a")

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
                user_id="user-a",
                status="running",
                step="fetching",
                message="Fetching collection data",
                created_at=previous_process_time,
                updated_at=previous_process_time,
                expires_at=previous_process_time + timedelta(hours=1),
            )
        )
        db.commit()

        active_job = service.get_active_job(db, user_id="user-a")
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
                user_id="user-a",
                status="running",
                step="fetching",
                message="Fetching collection data",
                created_at=previous_process_time,
                updated_at=previous_process_time,
                expires_at=previous_process_time + timedelta(hours=1),
            )
        )
        db.commit()

        expired_job = service.get_job(db, "orphaned-job", user_id="user-a")

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
    UserAccount.__table__.create(engine)
    CollectionSyncJob.__table__.create(engine)
    return sessionmaker(bind=engine)
