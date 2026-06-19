from collections.abc import Iterator
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.models.auth import (
    AuthSession,
    ConsumedRefreshToken,
    EmailVerificationCode,
    PasswordResetCode,
    UsageEvent,
    UserAccount,
    UserEntitlement,
)
from app.repositories.auth_repository import AuthRepository, normalize_email

AUTH_TABLES = [
    UserAccount.__table__,
    AuthSession.__table__,
    ConsumedRefreshToken.__table__,
    EmailVerificationCode.__table__,
    PasswordResetCode.__table__,
    UserEntitlement.__table__,
    UsageEvent.__table__,
]


@pytest.fixture()
def db_session() -> Iterator[Session]:
    engine = create_engine("sqlite:///:memory:")
    for table in AUTH_TABLES:
        table.create(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        for table in reversed(AUTH_TABLES):
            table.drop(engine)


def test_create_user_account_normalizes_email_and_stores_hash_metadata(db_session: Session) -> None:
    repository = AuthRepository()

    account = repository.create_user_account(
        db_session,
        user_id="user-1",
        email="  Alex@Example.COM ",
        password_hash="argon2id$hash",
        password_hash_algorithm="argon2id",
        password_hash_version=2,
        password_hash_params={"memory_cost": 65536, "time_cost": 3},
    )

    assert account.id == "user-1"
    assert account.email == "Alex@Example.COM"
    assert account.normalized_email == "alex@example.com"
    assert account.password_hash_algorithm == "argon2id"
    assert account.password_hash_version == 2
    assert account.password_hash_params == {"memory_cost": 65536, "time_cost": 3}
    assert account.is_active is True
    assert account.email_verified_at is None
    assert repository.get_user_by_normalized_email(db_session, "ALEX@example.com") == account


def test_mark_email_verified_sets_verification_timestamp(db_session: Session) -> None:
    repository = AuthRepository()
    account = repository.create_user_account(
        db_session,
        user_id="user-1",
        email="alex@example.com",
        password_hash="hash",
        password_hash_algorithm="argon2id",
    )
    verified_at = datetime(2026, 6, 17, 12)

    repository.mark_email_verified(db_session, user=account, verified_at=verified_at)

    assert repository.get_user_by_id(db_session, "user-1").email_verified_at == verified_at


def test_create_touch_and_revoke_auth_session(db_session: Session) -> None:
    repository = AuthRepository()
    repository.create_user_account(
        db_session,
        user_id="user-1",
        email="alex@example.com",
        password_hash="hash",
        password_hash_algorithm="argon2id",
    )
    now = datetime(2026, 6, 17, 12)
    expires_at = now + timedelta(days=30)

    auth_session = repository.create_auth_session(
        db_session,
        session_id="session-1",
        user_id="user-1",
        refresh_token_hash="refresh-hash-1",
        device_label="Pixel",
        last_activity_at=now,
        expires_at=expires_at,
    )

    assert auth_session.device_label == "Pixel"
    assert repository.get_auth_session_by_refresh_token_hash(db_session, "refresh-hash-1") == auth_session

    touched_at = now + timedelta(minutes=5)
    repository.touch_auth_session(
        db_session,
        auth_session=auth_session,
        last_activity_at=touched_at,
        refresh_token_hash="refresh-hash-2",
        expires_at=expires_at + timedelta(days=1),
    )

    assert repository.get_auth_session_by_refresh_token_hash(db_session, "refresh-hash-1") is None
    assert repository.get_auth_session_by_refresh_token_hash(db_session, "refresh-hash-2") == auth_session
    assert auth_session.last_activity_at == touched_at

    revoked_at = touched_at + timedelta(minutes=1)
    repository.revoke_auth_session(
        db_session,
        auth_session=auth_session,
        revoked_at=revoked_at,
        reason="logout",
    )

    assert auth_session.revoked_at == revoked_at
    assert auth_session.revoke_reason == "logout"


def test_create_and_consume_email_verification_code(db_session: Session) -> None:
    repository = AuthRepository()
    repository.create_user_account(
        db_session,
        user_id="user-1",
        email="alex@example.com",
        password_hash="hash",
        password_hash_algorithm="argon2id",
    )
    expires_at = datetime(2026, 6, 17, 12) + timedelta(minutes=10)

    code = repository.create_email_verification_code(
        db_session,
        code_id="code-1",
        user_id="user-1",
        code_hash="email-code-hash",
        sent_to_email="alex@example.com",
        expires_at=expires_at,
        resend_count=1,
    )

    assert repository.get_email_verification_code_by_hash(db_session, "email-code-hash") == code
    assert code.resend_count == 1
    assert code.consumed_at is None

    consumed_at = expires_at - timedelta(minutes=1)
    repository.consume_email_verification_code(db_session, code=code, consumed_at=consumed_at)

    assert code.consumed_at == consumed_at


def test_get_latest_email_verification_code_orders_by_issue_time(db_session: Session) -> None:
    repository = AuthRepository()
    repository.create_user_account(
        db_session,
        user_id="user-1",
        email="alex@example.com",
        password_hash="hash",
        password_hash_algorithm="argon2id",
    )

    older_code = repository.create_email_verification_code(
        db_session,
        code_id="email-code-1",
        user_id="user-1",
        code_hash="email-code-hash-1",
        sent_to_email="alex@example.com",
        expires_at=datetime(2026, 6, 17, 13),
    )
    newer_code = repository.create_email_verification_code(
        db_session,
        code_id="email-code-2",
        user_id="user-1",
        code_hash="email-code-hash-2",
        sent_to_email="alex@example.com",
        expires_at=datetime(2026, 6, 17, 12, 10),
    )
    older_code.created_at = datetime(2026, 6, 17, 12)
    newer_code.created_at = datetime(2026, 6, 17, 12, 1)
    db_session.commit()

    assert repository.get_latest_email_verification_code(db_session, user_id="user-1") == newer_code


def test_create_and_consume_password_reset_code(db_session: Session) -> None:
    repository = AuthRepository()
    repository.create_user_account(
        db_session,
        user_id="user-1",
        email="alex@example.com",
        password_hash="hash",
        password_hash_algorithm="argon2id",
    )
    expires_at = datetime(2026, 6, 17, 12) + timedelta(minutes=15)

    code = repository.create_password_reset_code(
        db_session,
        code_id="reset-1",
        user_id="user-1",
        code_hash="reset-code-hash",
        sent_to_email="alex@example.com",
        expires_at=expires_at,
    )

    assert repository.get_password_reset_code_by_hash(db_session, "reset-code-hash") == code

    consumed_at = expires_at - timedelta(minutes=1)
    repository.consume_password_reset_code(db_session, code=code, consumed_at=consumed_at)

    assert code.consumed_at == consumed_at


def test_sum_usage_units_filters_by_user_capability_and_window(db_session: Session) -> None:
    repository = AuthRepository()
    repository.create_user_account(
        db_session,
        user_id="user-1",
        email="alex@example.com",
        password_hash="hash",
        password_hash_algorithm="argon2id",
    )
    repository.create_user_account(
        db_session,
        user_id="user-2",
        email="sam@example.com",
        password_hash="hash",
        password_hash_algorithm="argon2id",
    )
    now = datetime(2026, 6, 19, 12)
    repository.record_usage_event(
        db_session,
        user_id="user-1",
        capability="ocr_identify",
        units=2,
        occurred_at=now - timedelta(minutes=5),
    )
    repository.record_usage_event(
        db_session,
        user_id="user-1",
        capability="ocr_identify",
        units=3,
        occurred_at=now - timedelta(days=2),
    )
    repository.record_usage_event(
        db_session,
        user_id="user-1",
        capability="ai_chat",
        units=4,
        occurred_at=now,
    )
    repository.record_usage_event(
        db_session,
        user_id="user-2",
        capability="ocr_identify",
        units=5,
        occurred_at=now,
    )

    assert repository.sum_usage_units(db_session, user_id="user-1", capability="ocr_identify") == 5
    assert (
        repository.sum_usage_units(
            db_session,
            user_id="user-1",
            capability="ocr_identify",
            since=now - timedelta(days=1),
        )
        == 2
    )


def test_get_latest_password_reset_code_orders_by_issue_time(db_session: Session) -> None:
    repository = AuthRepository()
    repository.create_user_account(
        db_session,
        user_id="user-1",
        email="alex@example.com",
        password_hash="hash",
        password_hash_algorithm="argon2id",
    )

    older_code = repository.create_password_reset_code(
        db_session,
        code_id="reset-code-1",
        user_id="user-1",
        code_hash="reset-code-hash-1",
        sent_to_email="alex@example.com",
        expires_at=datetime(2026, 6, 17, 13),
    )
    newer_code = repository.create_password_reset_code(
        db_session,
        code_id="reset-code-2",
        user_id="user-1",
        code_hash="reset-code-hash-2",
        sent_to_email="alex@example.com",
        expires_at=datetime(2026, 6, 17, 12, 10),
    )
    older_code.created_at = datetime(2026, 6, 17, 12)
    newer_code.created_at = datetime(2026, 6, 17, 12, 1)
    db_session.commit()

    assert repository.get_latest_password_reset_code(db_session, user_id="user-1") == newer_code


def test_ensure_entitlement_upserts_plan_and_record_usage_event(db_session: Session) -> None:
    repository = AuthRepository()
    repository.create_user_account(
        db_session,
        user_id="user-1",
        email="alex@example.com",
        password_hash="hash",
        password_hash_algorithm="argon2id",
    )

    entitlement = repository.ensure_entitlement(db_session, user_id="user-1")

    assert entitlement.plan == "FREE"
    assert entitlement.status == "ACTIVE"

    updated = repository.ensure_entitlement(db_session, user_id="user-1", plan="PLUS", status="TRIAL")

    assert updated.user_id == "user-1"
    assert updated.plan == "PLUS"
    assert updated.status == "TRIAL"

    occurred_at = datetime(2026, 6, 17, 12)
    event = repository.record_usage_event(
        db_session,
        event_id="usage-1",
        user_id="user-1",
        capability="ocr_identify",
        units=2,
        occurred_at=occurred_at,
        event_metadata={"source": "test"},
    )

    assert event.user_id == "user-1"
    assert event.capability == "ocr_identify"
    assert event.units == 2
    assert event.event_metadata == {"source": "test"}


def test_lock_usage_counter_uses_postgres_transaction_advisory_lock() -> None:
    repository = AuthRepository()
    db_session = _FakeDialectSession("postgresql")

    repository.lock_usage_counter(db_session, user_id="user-1", capability="ocr_identify")

    assert len(db_session.executed) == 1
    statement, params = db_session.executed[0]
    assert "pg_advisory_xact_lock" in statement
    assert isinstance(params["key_1"], int)
    assert isinstance(params["key_2"], int)


def test_lock_usage_counter_is_noop_outside_postgres() -> None:
    repository = AuthRepository()
    db_session = _FakeDialectSession("sqlite")

    repository.lock_usage_counter(db_session, user_id="user-1", capability="ocr_identify")

    assert db_session.executed == []


def test_normalize_email_trims_and_casefolds() -> None:
    assert normalize_email("  USER@Example.COM  ") == "user@example.com"


class _FakeDialectSession:
    def __init__(self, dialect_name: str) -> None:
        self._bind = SimpleNamespace(dialect=SimpleNamespace(name=dialect_name))
        self.executed: list[tuple[str, dict]] = []

    def get_bind(self):
        return self._bind

    def execute(self, statement, params: dict) -> None:
        self.executed.append((str(statement), params))
