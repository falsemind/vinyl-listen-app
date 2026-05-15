from datetime import datetime

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.identify_job import IdentifyJob


class IdentifyJobRepository:
    @staticmethod
    def create(
        db: Session,
        *,
        job_id: str,
        status: str,
        message: str,
        client_key: str | None,
        filename: str,
        content_type: str,
        created_at: datetime,
        expires_at: datetime,
    ) -> IdentifyJob:
        job = IdentifyJob(
            id=job_id,
            status=status,
            client_key=client_key,
            message=message,
            filename=filename,
            content_type=content_type,
            created_at=created_at,
            updated_at=created_at,
            expires_at=expires_at,
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        return job

    @staticmethod
    def get(db: Session, job_id: str) -> IdentifyJob | None:
        return db.query(IdentifyJob).filter(IdentifyJob.id == job_id).one_or_none()

    @staticmethod
    def count_active_by_client(db: Session, *, client_key: str, active_statuses: set[str]) -> int:
        return (
            db.query(func.count(IdentifyJob.id))
            .filter(IdentifyJob.client_key == client_key)
            .filter(IdentifyJob.status.in_(active_statuses))
            .scalar()
            or 0
        )

    @staticmethod
    def count_active(db: Session, *, active_statuses: set[str]) -> int:
        return db.query(func.count(IdentifyJob.id)).filter(IdentifyJob.status.in_(active_statuses)).scalar() or 0

    @staticmethod
    def expire_stale_active(
        db: Session,
        *,
        active_statuses: set[str],
        stale_before: datetime,
        expires_at_or_before: datetime,
        updated_at: datetime,
    ) -> int:
        stale_jobs = (
            db.query(IdentifyJob)
            .filter(IdentifyJob.status.in_(active_statuses))
            .filter(
                or_(
                    IdentifyJob.updated_at <= stale_before,
                    IdentifyJob.expires_at <= expires_at_or_before,
                )
            )
            .all()
        )
        if not stale_jobs:
            return 0

        for job in stale_jobs:
            job.status = "expired"
            job.message = "Identify job expired before completion. Please retry."
            job.error = {
                "code": "identify_job_stale",
                "message": "Identify job expired before completion. Please retry.",
                "failed_step": "unknown",
            }
            job.updated_at = updated_at
            db.add(job)

        db.commit()
        return len(stale_jobs)

    @staticmethod
    def update_status(
        db: Session,
        job: IdentifyJob,
        *,
        status: str,
        message: str,
        updated_at: datetime,
    ) -> IdentifyJob:
        job.status = status
        job.message = message
        job.updated_at = updated_at
        db.add(job)
        db.commit()
        db.refresh(job)
        return job

    @staticmethod
    def complete(
        db: Session,
        job: IdentifyJob,
        *,
        result: dict,
        message: str,
        updated_at: datetime,
    ) -> IdentifyJob:
        job.status = "completed"
        job.message = message
        job.result = result
        job.error = None
        job.updated_at = updated_at
        db.add(job)
        db.commit()
        db.refresh(job)
        return job

    @staticmethod
    def fail(
        db: Session,
        job: IdentifyJob,
        *,
        error: dict,
        message: str,
        updated_at: datetime,
    ) -> IdentifyJob:
        job.status = "failed"
        job.message = message
        job.error = error
        job.updated_at = updated_at
        db.add(job)
        db.commit()
        db.refresh(job)
        return job
