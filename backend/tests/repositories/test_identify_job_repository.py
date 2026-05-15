from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.identify_job import IdentifyJob
from app.repositories.identify_job_repository import IdentifyJobRepository


def test_expire_stale_active_marks_only_stale_active_jobs() -> None:
    engine = create_engine("sqlite:///:memory:")
    IdentifyJob.__table__.create(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    now = datetime(2026, 5, 15, 12, 0, 0, tzinfo=UTC)

    with session_factory() as db:
        db.add_all(
            [
                _job(
                    "stale-active",
                    "upload_received",
                    client_key="client-a",
                    updated_at=now - timedelta(minutes=30),
                    expires_at=now + timedelta(hours=1),
                ),
                _job(
                    "fresh-active",
                    "upload_received",
                    client_key="client-b",
                    updated_at=now - timedelta(minutes=1),
                    expires_at=now + timedelta(hours=1),
                ),
                _job(
                    "completed-stale",
                    "completed",
                    client_key="client-c",
                    updated_at=now - timedelta(minutes=30),
                    expires_at=now + timedelta(hours=1),
                ),
            ]
        )
        db.commit()

        expired_count = IdentifyJobRepository.expire_stale_active(
            db,
            active_statuses={"upload_received"},
            stale_before=now - timedelta(minutes=15),
            expires_at_or_before=now,
            updated_at=now,
        )

        assert expired_count == 1
        assert db.get(IdentifyJob, "stale-active").status == "expired"
        assert db.get(IdentifyJob, "stale-active").error["code"] == "identify_job_stale"
        assert db.get(IdentifyJob, "fresh-active").status == "upload_received"
        assert db.get(IdentifyJob, "completed-stale").status == "completed"


def _job(
    job_id: str,
    status: str,
    *,
    client_key: str,
    updated_at: datetime,
    expires_at: datetime,
) -> IdentifyJob:
    return IdentifyJob(
        id=job_id,
        status=status,
        client_key=client_key,
        message="Message",
        filename="cover.jpg",
        content_type="image/jpeg",
        created_at=updated_at,
        updated_at=updated_at,
        expires_at=expires_at,
    )
