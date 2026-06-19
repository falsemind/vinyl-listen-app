from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.auth import UserAccount
from app.models.identify_job import IdentifyJob
from app.repositories.identify_job_repository import IdentifyJobRepository


def test_expire_stale_active_marks_only_stale_active_jobs() -> None:
    engine = create_engine("sqlite:///:memory:")
    UserAccount.__table__.create(engine)
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


def test_request_cancel_marks_active_job_without_changing_status() -> None:
    engine = create_engine("sqlite:///:memory:")
    UserAccount.__table__.create(engine)
    IdentifyJob.__table__.create(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    now = datetime(2026, 5, 15, 12, 0, 0, tzinfo=UTC)

    with session_factory() as db:
        db.add(
            _job(
                "active-job",
                "extracting_text",
                client_key="client-a",
                updated_at=now - timedelta(minutes=1),
                expires_at=now + timedelta(hours=1),
            )
        )
        db.commit()

        canceled_job = IdentifyJobRepository.request_cancel(
            db,
            "active-job",
            requested_at=now,
        )

        assert canceled_job is not None
        assert canceled_job.status == "extracting_text"
        assert canceled_job.cancel_requested_at == _stored_datetime(now)
        assert canceled_job.updated_at == _stored_datetime(now)
        assert IdentifyJobRepository.is_cancel_requested(db, "active-job") is True


def test_request_cancel_is_idempotent_and_preserves_first_request_time() -> None:
    engine = create_engine("sqlite:///:memory:")
    UserAccount.__table__.create(engine)
    IdentifyJob.__table__.create(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    now = datetime(2026, 5, 15, 12, 0, 0, tzinfo=UTC)
    first_requested_at = now - timedelta(seconds=30)

    with session_factory() as db:
        job = _job(
            "cancel-requested-job",
            "searching_discogs",
            client_key="client-a",
            updated_at=now - timedelta(minutes=1),
            expires_at=now + timedelta(hours=1),
        )
        job.cancel_requested_at = first_requested_at
        db.add(job)
        db.commit()

        canceled_job = IdentifyJobRepository.request_cancel(
            db,
            "cancel-requested-job",
            requested_at=now,
        )

        assert canceled_job is not None
        assert canceled_job.status == "searching_discogs"
        assert canceled_job.cancel_requested_at == _stored_datetime(first_requested_at)
        assert canceled_job.updated_at == _stored_datetime(now - timedelta(minutes=1))


def test_request_cancel_does_not_mutate_terminal_job() -> None:
    engine = create_engine("sqlite:///:memory:")
    UserAccount.__table__.create(engine)
    IdentifyJob.__table__.create(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    now = datetime(2026, 5, 15, 12, 0, 0, tzinfo=UTC)
    original_updated_at = now - timedelta(minutes=5)

    with session_factory() as db:
        db.add(
            _job(
                "completed-job",
                "completed",
                client_key="client-a",
                updated_at=original_updated_at,
                expires_at=now + timedelta(hours=1),
            )
        )
        db.commit()

        canceled_job = IdentifyJobRepository.request_cancel(
            db,
            "completed-job",
            requested_at=now,
        )

        assert canceled_job is not None
        assert canceled_job.status == "completed"
        assert canceled_job.cancel_requested_at is None
        assert canceled_job.updated_at == _stored_datetime(original_updated_at)
        assert IdentifyJobRepository.is_cancel_requested(db, "completed-job") is False


def test_mark_canceled_sets_terminal_status_without_failure_payload() -> None:
    engine = create_engine("sqlite:///:memory:")
    UserAccount.__table__.create(engine)
    IdentifyJob.__table__.create(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    now = datetime(2026, 5, 15, 12, 0, 0, tzinfo=UTC)

    with session_factory() as db:
        job = _job(
            "active-job",
            "parsing_identifiers",
            client_key="client-a",
            updated_at=now - timedelta(minutes=1),
            expires_at=now + timedelta(hours=1),
        )
        job.error = {"code": "previous_error", "message": "Previous", "failed_step": "unknown"}
        db.add(job)
        db.commit()

        canceled_job = IdentifyJobRepository.mark_canceled(
            db,
            job,
            message="Identify canceled",
            updated_at=now,
        )

        assert canceled_job.status == "canceled"
        assert canceled_job.message == "Identify canceled"
        assert canceled_job.error is None
        assert canceled_job.result is None
        assert canceled_job.cancel_requested_at == _stored_datetime(now)
        assert canceled_job.updated_at == _stored_datetime(now)


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
        user_id="user-a",
        status=status,
        client_key=client_key,
        message="Message",
        filename="cover.jpg",
        content_type="image/jpeg",
        created_at=updated_at,
        updated_at=updated_at,
        expires_at=expires_at,
    )


def _stored_datetime(value: datetime) -> datetime:
    return value.replace(tzinfo=None)
