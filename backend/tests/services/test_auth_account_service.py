import json
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

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
from app.repositories.auth_repository import AuthRepository
from app.services.auth_account_service import (
    AuthAccountService,
    EmailAlreadyRegisteredError,
    EmailVerificationCodeConsumedError,
    EmailVerificationCodeExpiredError,
    EmailVerificationCodeInvalidError,
    EmailVerificationResendRateLimitedError,
    PasswordResetCodeConsumedError,
    PasswordResetRequestRateLimitedError,
)
from app.services.auth_email_delivery import AuthEmailMessage, LocalDevEmailSender
from app.services.password_hashing import Argon2idPasswordHasher, PasswordHashConfig

AUTH_TABLES = [
    UserAccount.__table__,
    AuthSession.__table__,
    ConsumedRefreshToken.__table__,
    EmailVerificationCode.__table__,
    PasswordResetCode.__table__,
    UserEntitlement.__table__,
    UsageEvent.__table__,
]

FAST_HASH_CONFIG = PasswordHashConfig(
    time_cost=1,
    memory_cost=1024,
    parallelism=1,
    hash_len=16,
    salt_len=8,
)


class AuthTestClock:
    def __init__(self, value: datetime) -> None:
        self.value = value

    def now(self) -> datetime:
        return self.value

    def advance(self, delta: timedelta) -> None:
        self.value += delta


class RecordingEmailSender:
    def __init__(self) -> None:
        self.messages: list[AuthEmailMessage] = []

    def send(self, message: AuthEmailMessage) -> None:
        self.messages.append(message)


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


@pytest.fixture()
def repository() -> AuthRepository:
    return AuthRepository()


@pytest.fixture()
def clock() -> AuthTestClock:
    return AuthTestClock(datetime(2026, 6, 18, 12, tzinfo=UTC))


@pytest.fixture()
def email_sender() -> RecordingEmailSender:
    return RecordingEmailSender()


@pytest.fixture()
def service(
    repository: AuthRepository,
    clock: AuthTestClock,
    email_sender: RecordingEmailSender,
) -> AuthAccountService:
    return _service(repository=repository, clock=clock, email_sender=email_sender)


def test_register_account_stores_unverified_user_and_sends_local_code(
    db_session: Session,
    repository: AuthRepository,
    service: AuthAccountService,
    email_sender: RecordingEmailSender,
) -> None:
    result = service.register_account(db_session, email="  Alex@Example.COM ", password="password")

    account = repository.get_user_by_id(db_session, result.user_id)
    assert account is not None
    assert account.email == "Alex@Example.COM"
    assert account.normalized_email == "alex@example.com"
    assert account.email_verified_at is None
    assert result.verification_expires_at == datetime(2026, 6, 18, 12, 15)
    assert len(email_sender.messages) == 1
    assert email_sender.messages[0].purpose == "email_verification"
    assert email_sender.messages[0].to_email == "Alex@Example.COM"
    assert len(email_sender.messages[0].code) == 6


def test_register_account_rejects_duplicate_email(
    db_session: Session,
    service: AuthAccountService,
) -> None:
    service.register_account(db_session, email="alex@example.com", password="password")

    with pytest.raises(EmailAlreadyRegisteredError):
        service.register_account(db_session, email="ALEX@example.com", password="password")


def test_verify_email_consumes_code_and_marks_email_verified(
    db_session: Session,
    repository: AuthRepository,
    service: AuthAccountService,
    email_sender: RecordingEmailSender,
    clock: AuthTestClock,
) -> None:
    result = service.register_account(db_session, email="alex@example.com", password="password")
    code = email_sender.messages[0].code
    clock.advance(timedelta(minutes=1))

    account = service.verify_email(db_session, email="alex@example.com", code=code)

    assert account.id == result.user_id
    assert account.email_verified_at == datetime(2026, 6, 18, 12, 1)
    verification_code = repository.get_latest_email_verification_code(db_session, user_id=result.user_id)
    assert verification_code is not None
    assert verification_code.consumed_at == datetime(2026, 6, 18, 12, 1)


def test_verify_email_rejects_invalid_expired_and_consumed_codes(
    db_session: Session,
    service: AuthAccountService,
    email_sender: RecordingEmailSender,
    clock: AuthTestClock,
) -> None:
    service.register_account(db_session, email="alex@example.com", password="password")
    code = email_sender.messages[0].code

    with pytest.raises(EmailVerificationCodeInvalidError):
        service.verify_email(db_session, email="alex@example.com", code="000000")

    clock.advance(timedelta(minutes=16))
    with pytest.raises(EmailVerificationCodeExpiredError):
        service.verify_email(db_session, email="alex@example.com", code=code)

    service.register_account(db_session, email="sam@example.com", password="password")
    sam_code = email_sender.messages[1].code
    service.verify_email(db_session, email="sam@example.com", code=sam_code)
    with pytest.raises(EmailVerificationCodeConsumedError):
        service.verify_email(db_session, email="sam@example.com", code=sam_code)


def test_resend_email_verification_rate_limits_and_sends_new_code(
    db_session: Session,
    service: AuthAccountService,
    email_sender: RecordingEmailSender,
    clock: AuthTestClock,
) -> None:
    service.register_account(db_session, email="alex@example.com", password="password")
    first_code = email_sender.messages[0].code

    with pytest.raises(EmailVerificationResendRateLimitedError):
        service.resend_email_verification(db_session, email="alex@example.com")

    clock.advance(timedelta(seconds=61))
    result = service.resend_email_verification(db_session, email="alex@example.com")

    assert result.resend_count == 1
    assert len(email_sender.messages) == 2
    assert email_sender.messages[1].code != first_code


def test_password_reset_request_is_generic_for_unknown_email(
    db_session: Session,
    service: AuthAccountService,
    email_sender: RecordingEmailSender,
) -> None:
    result = service.request_password_reset(db_session, email="unknown@example.com")

    assert result.accepted is True
    assert result.email == "unknown@example.com"
    assert email_sender.messages == []


def test_password_reset_request_is_rate_limited_and_replaces_previous_code_after_cooldown(
    db_session: Session,
    repository: AuthRepository,
    service: AuthAccountService,
    email_sender: RecordingEmailSender,
    clock: AuthTestClock,
) -> None:
    registration = service.register_account(db_session, email="alex@example.com", password="password")
    service.request_password_reset(db_session, email="alex@example.com")
    first_reset_code = email_sender.messages[1].code

    with pytest.raises(PasswordResetRequestRateLimitedError):
        service.request_password_reset(db_session, email="alex@example.com")

    assert len(email_sender.messages) == 2

    clock.advance(timedelta(seconds=61))
    service.request_password_reset(db_session, email="alex@example.com")

    assert len(email_sender.messages) == 3
    assert email_sender.messages[2].code != first_reset_code
    latest_code = repository.get_latest_password_reset_code(db_session, user_id=registration.user_id)
    assert latest_code is not None
    assert latest_code.consumed_at is None

    with pytest.raises(PasswordResetCodeConsumedError):
        service.confirm_password_reset(
            db_session,
            email="alex@example.com",
            code=first_reset_code,
            new_password="new-password",
        )


def test_password_reset_confirm_updates_password_and_revokes_sessions(
    db_session: Session,
    repository: AuthRepository,
    service: AuthAccountService,
    email_sender: RecordingEmailSender,
    clock: AuthTestClock,
) -> None:
    registration = service.register_account(db_session, email="alex@example.com", password="old-password")
    repository.create_auth_session(
        db_session,
        user_id=registration.user_id,
        refresh_token_hash="refresh-hash",
        last_activity_at=datetime(2026, 6, 18, 12),
        expires_at=datetime(2026, 7, 18, 12),
    )
    service.request_password_reset(db_session, email="alex@example.com")
    reset_code = email_sender.messages[1].code
    clock.advance(timedelta(minutes=1))

    account = service.confirm_password_reset(
        db_session,
        email="alex@example.com",
        code=reset_code,
        new_password="new-password",
    )

    verification = Argon2idPasswordHasher(FAST_HASH_CONFIG).verify_password(
        password="new-password",
        password_hash=account.password_hash,
        algorithm=account.password_hash_algorithm,
        version=account.password_hash_version,
        params=account.password_hash_params,
    )
    assert verification.is_valid is True
    auth_session = repository.get_auth_session_by_refresh_token_hash(db_session, "refresh-hash")
    assert auth_session is not None
    assert auth_session.revoked_at == datetime(2026, 6, 18, 12, 1)
    assert auth_session.revoke_reason == "password_reset"


def test_local_dev_email_sender_writes_jsonl_outbox(tmp_path) -> None:
    outbox_path = tmp_path / "auth-outbox.jsonl"
    sender = LocalDevEmailSender(outbox_path)

    sender.send(
        AuthEmailMessage(
            to_email="alex@example.com",
            subject="Verify",
            body="Code 123456",
            purpose="email_verification",
            code="123456",
        )
    )

    rows = [json.loads(line) for line in outbox_path.read_text(encoding="utf-8").splitlines()]
    assert rows == [
        {
            "body": "Code 123456",
            "code": "123456",
            "purpose": "email_verification",
            "sent_at": rows[0]["sent_at"],
            "subject": "Verify",
            "to_email": "alex@example.com",
        }
    ]


def _service(
    *,
    repository: AuthRepository,
    clock: AuthTestClock,
    email_sender: RecordingEmailSender,
) -> AuthAccountService:
    return AuthAccountService(
        repository=repository,
        password_hasher=Argon2idPasswordHasher(FAST_HASH_CONFIG),
        email_sender=email_sender,
        code_hash_secret="test-code-secret",
        now_provider=clock.now,
        verification_code_ttl=timedelta(minutes=15),
        password_reset_code_ttl=timedelta(minutes=15),
        resend_cooldown=timedelta(seconds=60),
    )
