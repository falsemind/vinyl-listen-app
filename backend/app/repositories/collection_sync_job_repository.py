from datetime import datetime

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.collection_sync_job import CollectionSyncJob

ACTIVE_COLLECTION_SYNC_JOB_STATUSES = {"queued", "running"}


class CollectionSyncJobRepository:
    @staticmethod
    def create(
        db: Session,
        *,
        job_id: str,
        user_id: str,
        status: str,
        message: str,
        created_at: datetime,
        expires_at: datetime,
    ) -> CollectionSyncJob:
        job = CollectionSyncJob(
            id=job_id,
            user_id=user_id,
            status=status,
            step=None,
            message=message,
            total_items=0,
            processed_items=0,
            added_count=0,
            updated_count=0,
            removed_count=0,
            created_at=created_at,
            updated_at=created_at,
            expires_at=expires_at,
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        return job

    @staticmethod
    def get(db: Session, job_id: str, *, user_id: str | None = None) -> CollectionSyncJob | None:
        query = db.query(CollectionSyncJob).filter(CollectionSyncJob.id == job_id)
        if user_id is not None:
            query = query.filter(CollectionSyncJob.user_id == user_id)
        return query.one_or_none()

    @staticmethod
    def get_active(db: Session, *, user_id: str) -> CollectionSyncJob | None:
        return (
            db.query(CollectionSyncJob)
            .filter(CollectionSyncJob.user_id == user_id)
            .filter(CollectionSyncJob.status.in_(ACTIVE_COLLECTION_SYNC_JOB_STATUSES))
            .order_by(CollectionSyncJob.created_at.desc())
            .first()
        )

    @staticmethod
    def expire_stale_active(
        db: Session,
        *,
        user_id: str | None = None,
        stale_before: datetime,
        expires_at_or_before: datetime,
        updated_at: datetime,
    ) -> int:
        stale_jobs = (
            db.query(CollectionSyncJob)
            .filter(CollectionSyncJob.status.in_(ACTIVE_COLLECTION_SYNC_JOB_STATUSES))
            .filter(
                or_(
                    CollectionSyncJob.updated_at <= stale_before,
                    CollectionSyncJob.expires_at <= expires_at_or_before,
                )
            )
        )
        if user_id is not None:
            stale_jobs = stale_jobs.filter(CollectionSyncJob.user_id == user_id)
        stale_jobs = stale_jobs.all()
        if not stale_jobs:
            return 0

        for job in stale_jobs:
            job.status = "expired"
            job.message = "Collection sync expired. Start a new sync."
            job.error = {
                "code": "collection_sync_job_stale",
                "message": "Collection sync expired. Start a new sync.",
                "failed_step": job.step or "unknown",
            }
            job.updated_at = updated_at
            db.add(job)

        db.commit()
        return len(stale_jobs)

    @staticmethod
    def update_progress(
        db: Session,
        job: CollectionSyncJob,
        *,
        step: str,
        message: str,
        updated_at: datetime,
        total_items: int | None = None,
        processed_items: int | None = None,
        added_count: int | None = None,
        updated_count: int | None = None,
        removed_count: int | None = None,
        commit: bool = True,
    ) -> CollectionSyncJob:
        job.status = "running"
        job.step = step
        job.message = message
        job.updated_at = updated_at
        if total_items is not None:
            job.total_items = total_items
        if processed_items is not None:
            job.processed_items = processed_items
        if added_count is not None:
            job.added_count = added_count
        if updated_count is not None:
            job.updated_count = updated_count
        if removed_count is not None:
            job.removed_count = removed_count

        db.add(job)
        if commit:
            db.commit()
            db.refresh(job)
        else:
            db.flush()
        return job

    @staticmethod
    def complete(
        db: Session,
        job: CollectionSyncJob,
        *,
        message: str,
        updated_at: datetime,
        total_items: int,
        processed_items: int,
        added_count: int,
        updated_count: int,
        removed_count: int,
    ) -> CollectionSyncJob:
        job.status = "succeeded"
        job.step = "loading"
        job.message = message
        job.total_items = total_items
        job.processed_items = processed_items
        job.added_count = added_count
        job.updated_count = updated_count
        job.removed_count = removed_count
        job.error = None
        job.updated_at = updated_at
        db.add(job)
        db.commit()
        db.refresh(job)
        return job

    @staticmethod
    def fail(
        db: Session,
        job: CollectionSyncJob,
        *,
        error: dict,
        message: str,
        updated_at: datetime,
    ) -> CollectionSyncJob:
        job.status = "failed"
        job.message = message
        job.error = error
        job.updated_at = updated_at
        db.add(job)
        db.commit()
        db.refresh(job)
        return job
