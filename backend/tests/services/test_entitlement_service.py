from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.models.auth import UsageEvent, UserAccount, UserEntitlement
from app.repositories.auth_repository import AuthRepository
from app.services.entitlement_service import (
    OCR_IDENTIFY_CAPABILITY,
    CapabilityRule,
    EntitlementService,
    FeatureGateError,
)


@pytest.fixture()
def db_session() -> Iterator[Session]:
    engine = create_engine("sqlite:///:memory:")
    UserAccount.__table__.create(engine)
    UserEntitlement.__table__.create(engine)
    UsageEvent.__table__.create(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = session_factory()
    session.add(
        UserAccount(
            id="user-a",
            email="user-a@example.com",
            normalized_email="user-a@example.com",
            password_hash="hash",
            password_hash_algorithm="argon2id",
        )
    )
    session.commit()
    try:
        yield session
    finally:
        session.close()
        UsageEvent.__table__.drop(engine)
        UserEntitlement.__table__.drop(engine)
        UserAccount.__table__.drop(engine)


def test_consume_usage_creates_default_entitlement_and_records_event(db_session: Session) -> None:
    now = datetime(2026, 6, 19, 12, 0, 0, tzinfo=UTC)
    service = _build_service(now=now)

    grant = service.consume_usage(
        db_session,
        user_id="user-a",
        capability=OCR_IDENTIFY_CAPABILITY,
        event_metadata={"source": "sync_identify"},
    )

    assert grant.plan == "FREE"
    assert grant.used_before == 0
    assert grant.used_after == 1
    assert grant.limit == 2
    assert db_session.get(UserEntitlement, "user-a").plan == "FREE"
    event = db_session.query(UsageEvent).one()
    assert event.user_id == "user-a"
    assert event.capability == OCR_IDENTIFY_CAPABILITY
    assert event.units == 1
    assert event.event_metadata == {"source": "sync_identify"}


def test_consume_usage_rejects_over_limit_without_recording_event(db_session: Session) -> None:
    now = datetime(2026, 6, 19, 12, 0, 0, tzinfo=UTC)
    service = _build_service(now=now)
    for _ in range(2):
        service.consume_usage(db_session, user_id="user-a", capability=OCR_IDENTIFY_CAPABILITY)

    with pytest.raises(FeatureGateError) as error:
        service.consume_usage(db_session, user_id="user-a", capability=OCR_IDENTIFY_CAPABILITY)

    assert error.value.code == "feature_usage_limit_exceeded"
    assert error.value.limit == 2
    assert error.value.used == 2
    assert db_session.query(UsageEvent).count() == 2


def test_consume_usage_ignores_events_outside_window(db_session: Session) -> None:
    now = datetime(2026, 6, 19, 12, 0, 0, tzinfo=UTC)
    service = _build_service(now=now)
    db_session.add(
        UsageEvent(
            id="old-usage",
            user_id="user-a",
            capability=OCR_IDENTIFY_CAPABILITY,
            units=2,
            occurred_at=now - timedelta(days=2),
        )
    )
    db_session.commit()

    grant = service.consume_usage(db_session, user_id="user-a", capability=OCR_IDENTIFY_CAPABILITY)

    assert grant.used_before == 0
    assert grant.used_after == 1
    assert db_session.query(UsageEvent).count() == 2


def test_plus_plan_has_no_usage_limit(db_session: Session) -> None:
    now = datetime(2026, 6, 19, 12, 0, 0, tzinfo=UTC)
    service = _build_service(now=now)
    db_session.add(UserEntitlement(user_id="user-a", plan="PLUS", status="ACTIVE"))
    db_session.commit()

    for _ in range(3):
        grant = service.consume_usage(db_session, user_id="user-a", capability=OCR_IDENTIFY_CAPABILITY)

    assert grant.plan == "PLUS"
    assert grant.limit is None
    assert db_session.query(UsageEvent).count() == 3


def test_expired_entitlement_blocks_usage_without_recording_event(db_session: Session) -> None:
    now = datetime(2026, 6, 19, 12, 0, 0, tzinfo=UTC)
    service = _build_service(now=now)
    db_session.add(
        UserEntitlement(
            user_id="user-a",
            plan="FREE",
            status="ACTIVE",
            valid_until=now - timedelta(seconds=1),
        )
    )
    db_session.commit()

    with pytest.raises(FeatureGateError) as error:
        service.consume_usage(db_session, user_id="user-a", capability=OCR_IDENTIFY_CAPABILITY)

    assert error.value.code == "feature_not_available"
    assert db_session.query(UsageEvent).count() == 0


def test_consume_usage_locks_counter_before_reading_usage() -> None:
    now = datetime(2026, 6, 19, 12, 0, 0, tzinfo=UTC)
    repository = _OrderingRepository()
    service = EntitlementService(
        repository=repository,
        now_provider=lambda: now,
        rules={
            OCR_IDENTIFY_CAPABILITY: CapabilityRule(
                capability=OCR_IDENTIFY_CAPABILITY,
                window=timedelta(days=1),
                plan_limits={"FREE": 25},
                default_limit=25,
            )
        },
    )
    db_session = _FakeSession()

    service.consume_usage(db_session, user_id="user-a", capability=OCR_IDENTIFY_CAPABILITY)

    assert repository.events == ["lock", "get_entitlement", "sum", "get_entitlement", "record"]
    assert db_session.commits == 1
    assert db_session.rollbacks == 0


def test_consume_usage_rolls_back_when_limit_is_denied() -> None:
    now = datetime(2026, 6, 19, 12, 0, 0, tzinfo=UTC)
    repository = _OrderingRepository(used_units=25)
    service = EntitlementService(
        repository=repository,
        now_provider=lambda: now,
        rules={
            OCR_IDENTIFY_CAPABILITY: CapabilityRule(
                capability=OCR_IDENTIFY_CAPABILITY,
                window=timedelta(days=1),
                plan_limits={"FREE": 25},
                default_limit=25,
            )
        },
    )
    db_session = _FakeSession()

    with pytest.raises(FeatureGateError):
        service.consume_usage(db_session, user_id="user-a", capability=OCR_IDENTIFY_CAPABILITY)

    assert repository.events == ["lock", "get_entitlement", "sum"]
    assert db_session.commits == 0
    assert db_session.rollbacks == 1


def _build_service(*, now: datetime) -> EntitlementService:
    return EntitlementService(
        now_provider=lambda: now,
        rules={
            OCR_IDENTIFY_CAPABILITY: CapabilityRule(
                capability=OCR_IDENTIFY_CAPABILITY,
                window=timedelta(days=1),
                plan_limits={"FREE": 2, "PLUS": None},
                default_limit=2,
            )
        },
    )


class _OrderingRepository(AuthRepository):
    def __init__(self, *, used_units: int = 24) -> None:
        self.events: list[str] = []
        self.used_units = used_units
        self.entitlement = UserEntitlement(user_id="user-a", plan="FREE", status="ACTIVE")

    def lock_usage_counter(self, db: Session, *, user_id: str, capability: str) -> None:
        _ = (db, user_id, capability)
        self.events.append("lock")

    def get_entitlement(self, db: Session, user_id: str) -> UserEntitlement | None:
        _ = (db, user_id)
        self.events.append("get_entitlement")
        return self.entitlement

    def sum_usage_units(
        self,
        db: Session,
        *,
        user_id: str,
        capability: str,
        since: datetime | None = None,
    ) -> int:
        _ = (db, user_id, capability, since)
        assert self.events[0] == "lock"
        self.events.append("sum")
        return self.used_units

    def record_usage_event(
        self,
        db: Session,
        *,
        user_id: str,
        capability: str,
        occurred_at: datetime,
        units: int = 1,
        event_metadata: dict | None = None,
        event_id: str | None = None,
        commit: bool = True,
    ) -> UsageEvent:
        _ = (db, user_id, capability, occurred_at, event_metadata, event_id, commit)
        self.events.append("record")
        return UsageEvent(
            id="usage-1",
            user_id=user_id,
            capability=capability,
            units=units,
            occurred_at=occurred_at,
        )


class _FakeSession:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1
