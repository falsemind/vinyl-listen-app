import json
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.models.ai_chat import AiChatMessageRecord, AiChatSession
from app.models.auth import (
    AccountDeletionAudit,
    AuthAuditEvent,
    AuthSession,
    ConsumedRefreshToken,
    EmailVerificationCode,
    PasswordResetCode,
    UsageEvent,
    UserAccount,
    UserEntitlement,
)
from app.models.collection_folders import CollectionFolder, ReleaseCollectionFolder, ReleaseCollectionMembership
from app.models.collection_settings import CollectionSettings
from app.models.collection_sync_job import CollectionSyncJob
from app.models.identify_job import IdentifyJob
from app.models.provider_integration import ProviderIntegration
from app.models.releases import Releases
from app.models.sessions import SessionGroups, Sessions, SessionTracks
from app.models.sessions_moods import SessionsMoods
from app.models.spotify_listening import SpotifyArtistStats, SpotifyListeningImportBatch
from app.repositories.auth_repository import AuthRepository
from app.services.auth_account_service import (
    AuthAccountService,
    DeleteAccountInvalidPasswordError,
    EmailAlreadyRegisteredError,
    EmailVerificationAttemptRateLimitedError,
    EmailVerificationCodeConsumedError,
    EmailVerificationCodeExpiredError,
    EmailVerificationCodeInvalidError,
    EmailVerificationResendRateLimitedError,
    PasswordChangeInvalidCurrentPasswordError,
    PasswordResetAttemptRateLimitedError,
    PasswordResetCodeConsumedError,
    PasswordResetCodeInvalidError,
    PasswordResetRequestRateLimitedError,
)
from app.services.auth_email_delivery import (
    AuthEmailDeliveryError,
    AuthEmailMessage,
    AuthEmailSender,
    LocalDevEmailSender,
)
from app.services.password_hashing import Argon2idPasswordHasher, PasswordHashConfig

AUTH_TABLES = [
    UserAccount.__table__,
    AccountDeletionAudit.__table__,
    AuthAuditEvent.__table__,
    AuthSession.__table__,
    ConsumedRefreshToken.__table__,
    EmailVerificationCode.__table__,
    PasswordResetCode.__table__,
    UserEntitlement.__table__,
    UsageEvent.__table__,
]

ACCOUNT_DELETE_TABLES = [
    ProviderIntegration.__table__,
    CollectionSettings.__table__,
    CollectionFolder.__table__,
    ReleaseCollectionMembership.__table__,
    ReleaseCollectionFolder.__table__,
    CollectionSyncJob.__table__,
    IdentifyJob.__table__,
    AiChatSession.__table__,
    AiChatMessageRecord.__table__,
    SpotifyListeningImportBatch.__table__,
    SpotifyArtistStats.__table__,
    SessionGroups.__table__,
    Sessions.__table__,
    SessionTracks.__table__,
    SessionsMoods.__table__,
]

_ = Releases.__table__

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


class FailingEmailSender:
    def send(self, message: AuthEmailMessage) -> None:
        _ = message
        raise AuthEmailDeliveryError("delivery failed")


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
    audit_event = db_session.query(AuthAuditEvent).filter_by(event_type="account_registered").one()
    assert audit_event.user_id == result.user_id
    assert audit_event.outcome == "success"
    assert audit_event.event_details == {"email_verification_required": True}
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


def test_verify_email_rate_limits_repeated_wrong_codes_per_account(
    db_session: Session,
    repository: AuthRepository,
    email_sender: RecordingEmailSender,
    clock: AuthTestClock,
) -> None:
    limited_service = _service(
        repository=repository,
        clock=clock,
        email_sender=email_sender,
        code_failed_attempt_limit=2,
        code_failed_attempt_lock=timedelta(minutes=5),
    )
    result = limited_service.register_account(db_session, email="alex@example.com", password="password")
    correct_code = email_sender.messages[0].code

    with pytest.raises(EmailVerificationCodeInvalidError):
        limited_service.verify_email(db_session, email="alex@example.com", code="000000")
    with pytest.raises(EmailVerificationCodeInvalidError):
        limited_service.verify_email(db_session, email="alex@example.com", code="111111")
    with pytest.raises(EmailVerificationAttemptRateLimitedError):
        limited_service.verify_email(db_session, email="alex@example.com", code=correct_code)

    latest_code = repository.get_latest_email_verification_code(db_session, user_id=result.user_id)
    assert latest_code is not None
    assert latest_code.failed_attempt_count == 2
    assert latest_code.failed_attempt_limited_until == datetime(2026, 6, 18, 12, 5)

    clock.advance(timedelta(minutes=5, seconds=1))
    account = limited_service.verify_email(db_session, email="alex@example.com", code=correct_code)

    assert account.email_verified_at == datetime(2026, 6, 18, 12, 5, 1)


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


def test_password_reset_request_is_generic_when_delivery_fails(
    db_session: Session,
    repository: AuthRepository,
    clock: AuthTestClock,
) -> None:
    setup_sender = RecordingEmailSender()
    setup_service = _service(repository=repository, clock=clock, email_sender=setup_sender)
    setup_service.register_account(db_session, email="alex@example.com", password="password")
    failing_service = _service(repository=repository, clock=clock, email_sender=FailingEmailSender())

    result = failing_service.request_password_reset(db_session, email="alex@example.com")

    assert result.accepted is True
    assert result.email == "alex@example.com"
    assert len(setup_sender.messages) == 1


def test_password_reset_request_echoes_input_email_casing(
    db_session: Session,
    repository: AuthRepository,
    clock: AuthTestClock,
    email_sender: RecordingEmailSender,
) -> None:
    service = _service(repository=repository, clock=clock, email_sender=email_sender)
    service.register_account(db_session, email="Alex@Example.COM", password="password")

    result = service.request_password_reset(db_session, email="alex@example.com")

    assert result.accepted is True
    assert result.email == "alex@example.com"
    assert email_sender.messages[1].to_email == "Alex@Example.COM"


def test_password_reset_confirm_rate_limits_repeated_wrong_codes_per_account(
    db_session: Session,
    repository: AuthRepository,
    email_sender: RecordingEmailSender,
    clock: AuthTestClock,
) -> None:
    limited_service = _service(
        repository=repository,
        clock=clock,
        email_sender=email_sender,
        code_failed_attempt_limit=2,
        code_failed_attempt_lock=timedelta(minutes=5),
    )
    registration = limited_service.register_account(db_session, email="alex@example.com", password="old-password")
    limited_service.request_password_reset(db_session, email="alex@example.com")
    correct_code = email_sender.messages[1].code

    with pytest.raises(PasswordResetCodeInvalidError):
        limited_service.confirm_password_reset(
            db_session,
            email="alex@example.com",
            code="000000",
            new_password="new-password",
        )
    with pytest.raises(PasswordResetCodeInvalidError):
        limited_service.confirm_password_reset(
            db_session,
            email="alex@example.com",
            code="111111",
            new_password="new-password",
        )
    with pytest.raises(PasswordResetAttemptRateLimitedError):
        limited_service.confirm_password_reset(
            db_session,
            email="alex@example.com",
            code=correct_code,
            new_password="new-password",
        )

    latest_code = repository.get_latest_password_reset_code(db_session, user_id=registration.user_id)
    assert latest_code is not None
    assert latest_code.failed_attempt_count == 2
    assert latest_code.failed_attempt_limited_until == datetime(2026, 6, 18, 12, 5)

    clock.advance(timedelta(minutes=5, seconds=1))
    account = limited_service.confirm_password_reset(
        db_session,
        email="alex@example.com",
        code=correct_code,
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


def test_password_reset_confirm_accepts_newest_code_when_older_code_expires_later(
    db_session: Session,
    repository: AuthRepository,
    email_sender: RecordingEmailSender,
    clock: AuthTestClock,
) -> None:
    long_ttl_service = _service(
        repository=repository,
        clock=clock,
        email_sender=email_sender,
        password_reset_code_ttl=timedelta(hours=1),
    )
    short_ttl_service = _service(
        repository=repository,
        clock=clock,
        email_sender=email_sender,
        password_reset_code_ttl=timedelta(minutes=5),
    )
    long_ttl_service.register_account(db_session, email="alex@example.com", password="old-password")
    long_ttl_service.request_password_reset(db_session, email="alex@example.com")
    older_reset_code = email_sender.messages[1].code
    clock.advance(timedelta(minutes=1))
    long_ttl_service.confirm_password_reset(
        db_session,
        email="alex@example.com",
        code=older_reset_code,
        new_password="intermediate-password",
    )

    clock.advance(timedelta(seconds=61))
    short_ttl_service.request_password_reset(db_session, email="alex@example.com")
    newer_reset_code = email_sender.messages[2].code
    clock.advance(timedelta(minutes=1))

    account = short_ttl_service.confirm_password_reset(
        db_session,
        email="alex@example.com",
        code=newer_reset_code,
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


def test_change_password_updates_hash_and_revokes_other_sessions(
    db_session: Session,
    repository: AuthRepository,
    service: AuthAccountService,
    email_sender: RecordingEmailSender,
    clock: AuthTestClock,
) -> None:
    registration = service.register_account(db_session, email="alex@example.com", password="old-password")
    user = repository.get_user_by_id(db_session, registration.user_id)
    assert user is not None
    current_session = repository.create_auth_session(
        db_session,
        session_id="session-current",
        user_id=user.id,
        refresh_token_hash="refresh-current",
        last_activity_at=datetime(2026, 6, 18, 12),
        expires_at=datetime(2026, 7, 18, 12),
    )
    other_session = repository.create_auth_session(
        db_session,
        session_id="session-other",
        user_id=user.id,
        refresh_token_hash="refresh-other",
        last_activity_at=datetime(2026, 6, 18, 12),
        expires_at=datetime(2026, 7, 18, 12),
    )
    clock.advance(timedelta(minutes=2))

    result = service.change_password(
        db_session,
        user=user,
        current_password="old-password",
        new_password="new-password",
        current_session_id=current_session.id,
    )

    verification = Argon2idPasswordHasher(FAST_HASH_CONFIG).verify_password(
        password="new-password",
        password_hash=result.user.password_hash,
        algorithm=result.user.password_hash_algorithm,
        version=result.user.password_hash_version,
        params=result.user.password_hash_params,
    )
    assert verification.is_valid is True
    assert result.revoked_sessions == 1
    assert current_session.revoked_at is None
    assert other_session.revoked_at == datetime(2026, 6, 18, 12, 2)
    assert other_session.revoke_reason == "password_change"
    audit_event = db_session.query(AuthAuditEvent).filter_by(event_type="password_changed").one()
    assert audit_event.user_id == user.id
    assert audit_event.session_id == "session-current"
    assert audit_event.outcome == "success"
    assert audit_event.event_details == {"revoked_sessions": 1, "sign_out_everywhere": False}
    assert email_sender.messages[-1].purpose == "password_change_notification"
    assert email_sender.messages[-1].to_email == "alex@example.com"
    assert email_sender.messages[-1].code is None
    assert "2026-06-18T12:02:00+00:00" in email_sender.messages[-1].body


def test_change_password_can_sign_out_everywhere_and_rejects_wrong_current_password(
    db_session: Session,
    repository: AuthRepository,
    service: AuthAccountService,
    email_sender: RecordingEmailSender,
    clock: AuthTestClock,
) -> None:
    registration = service.register_account(db_session, email="alex@example.com", password="old-password")
    user = repository.get_user_by_id(db_session, registration.user_id)
    assert user is not None
    auth_session = repository.create_auth_session(
        db_session,
        session_id="session-current",
        user_id=user.id,
        refresh_token_hash="refresh-current",
        last_activity_at=datetime(2026, 6, 18, 12),
        expires_at=datetime(2026, 7, 18, 12),
    )

    with pytest.raises(PasswordChangeInvalidCurrentPasswordError):
        service.change_password(
            db_session,
            user=user,
            current_password="wrong-password",
            new_password="new-password",
            current_session_id=auth_session.id,
        )
    assert [message.purpose for message in email_sender.messages] == ["email_verification"]

    clock.advance(timedelta(minutes=3))
    result = service.change_password(
        db_session,
        user=user,
        current_password="old-password",
        new_password="new-password",
        current_session_id=auth_session.id,
        sign_out_everywhere=True,
    )

    assert result.revoked_sessions == 1
    assert auth_session.revoked_at == datetime(2026, 6, 18, 12, 3)
    assert auth_session.revoke_reason == "password_change"
    failed_event = db_session.query(AuthAuditEvent).filter_by(event_type="password_changed", outcome="failure").one()
    assert failed_event.user_id == user.id
    assert failed_event.event_details == {"reason": "invalid_current_password"}
    assert [message.purpose for message in email_sender.messages] == [
        "email_verification",
        "password_change_notification",
    ]


def test_change_password_succeeds_when_security_notification_fails(
    db_session: Session,
    repository: AuthRepository,
    clock: AuthTestClock,
) -> None:
    setup_sender = RecordingEmailSender()
    setup_service = _service(repository=repository, clock=clock, email_sender=setup_sender)
    registration = setup_service.register_account(db_session, email="alex@example.com", password="old-password")
    user = repository.get_user_by_id(db_session, registration.user_id)
    assert user is not None
    auth_session = repository.create_auth_session(
        db_session,
        session_id="session-current",
        user_id=user.id,
        refresh_token_hash="refresh-current",
        last_activity_at=datetime(2026, 6, 18, 12),
        expires_at=datetime(2026, 7, 18, 12),
    )
    failing_service = _service(repository=repository, clock=clock, email_sender=FailingEmailSender())
    clock.advance(timedelta(minutes=4))

    result = failing_service.change_password(
        db_session,
        user=user,
        current_password="old-password",
        new_password="new-password",
        current_session_id=auth_session.id,
    )

    verification = Argon2idPasswordHasher(FAST_HASH_CONFIG).verify_password(
        password="new-password",
        password_hash=result.user.password_hash,
        algorithm=result.user.password_hash_algorithm,
        version=result.user.password_hash_version,
        params=result.user.password_hash_params,
    )
    assert verification.is_valid is True


def test_delete_account_requires_password_and_hard_deletes_owned_data(
    db_session: Session,
    repository: AuthRepository,
    service: AuthAccountService,
) -> None:
    _create_account_delete_tables(db_session)
    try:
        registration = service.register_account(db_session, email="alex@example.com", password="password")
        user = repository.get_user_by_id(db_session, registration.user_id)
        assert user is not None

        with pytest.raises(DeleteAccountInvalidPasswordError):
            service.delete_account(db_session, user=user, password="wrong-password")

        _seed_account_owned_data(db_session, repository=repository, user_id=user.id)
        result = service.delete_account(db_session, user=user, password="password")

        assert repository.get_user_by_id(db_session, user.id) is None
        audit = db_session.query(AccountDeletionAudit).one()
        assert audit.id == result.deletion_receipt_id
        assert audit.event_type == "account_deleted"
        assert set(AccountDeletionAudit.__table__.columns.keys()) == {
            "id",
            "event_type",
            "requested_at",
            "deleted_at",
            "created_at",
        }
        for model in (
            AuthAuditEvent,
            AuthSession,
            ConsumedRefreshToken,
            ProviderIntegration,
            CollectionSettings,
            ReleaseCollectionFolder,
            ReleaseCollectionMembership,
            CollectionFolder,
            CollectionSyncJob,
            IdentifyJob,
            AiChatMessageRecord,
            AiChatSession,
            SpotifyListeningImportBatch,
            SpotifyArtistStats,
            SessionTracks,
            Sessions,
            SessionGroups,
            SessionsMoods,
            UsageEvent,
            UserEntitlement,
            EmailVerificationCode,
        ):
            assert db_session.query(model).count() == 0
    finally:
        _drop_account_delete_tables(db_session)


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


def _create_account_delete_tables(db_session: Session) -> None:
    bind = db_session.get_bind()
    for table in ACCOUNT_DELETE_TABLES:
        table.create(bind, checkfirst=True)


def _drop_account_delete_tables(db_session: Session) -> None:
    bind = db_session.get_bind()
    for table in reversed(ACCOUNT_DELETE_TABLES):
        table.drop(bind, checkfirst=True)


def _seed_account_owned_data(db_session: Session, *, repository: AuthRepository, user_id: str) -> None:
    now = datetime(2026, 6, 18, 12, tzinfo=UTC)
    auth_session = repository.create_auth_session(
        db_session,
        session_id="session-delete",
        user_id=user_id,
        refresh_token_hash="refresh-delete",
        last_activity_at=now,
        expires_at=now + timedelta(days=30),
        commit=False,
    )
    repository.create_consumed_refresh_token(
        db_session,
        session_id=auth_session.id,
        user_id=user_id,
        refresh_token_hash="consumed-refresh-delete",
        consumed_at=now,
        expires_at=now + timedelta(days=30),
        commit=False,
    )
    repository.ensure_entitlement(db_session, user_id=user_id, commit=False)
    repository.record_usage_event(
        db_session,
        user_id=user_id,
        capability="ocr_identify",
        occurred_at=now,
        commit=False,
    )

    folder = CollectionFolder(user_id=user_id, discogs_folder_id=1, name="All", is_default=True)
    chat_session = AiChatSession(
        id="chat-delete",
        user_id=user_id,
        public_conversation_id="conversation-delete",
        created_at=now,
        updated_at=now,
    )
    session_group = SessionGroups(
        id="group-delete",
        user_id=user_id,
        status="active",
        style_focus="mixed",
        mood_direction="steady_mood",
        session_type="casual_listening",
        started_at=now,
    )
    listening_session = Sessions(
        id="listen-delete",
        release_id="release-delete",
        user_id=user_id,
        session_group_id=session_group.id,
        played_at=now,
    )
    db_session.add_all(
        [
            ProviderIntegration(
                provider="discogs",
                user_id=user_id,
                access_token_ciphertext="encrypted-token",
                external_user_id="discogs-user",
                external_username="alex",
            ),
            CollectionSettings(user_id=user_id, source_of_truth="DISCOGS"),
            folder,
            ReleaseCollectionMembership(user_id=user_id, release_id="release-delete", in_collection=True),
            CollectionSyncJob(
                id="sync-delete",
                user_id=user_id,
                status="queued",
                message="Queued",
                expires_at=now + timedelta(hours=1),
            ),
            IdentifyJob(
                id="identify-delete",
                user_id=user_id,
                status="queued",
                message="Queued",
                filename="cover.jpg",
                content_type="image/jpeg",
                expires_at=now + timedelta(hours=1),
            ),
            chat_session,
            AiChatMessageRecord(conversation_id=chat_session.id, role="user", content="hello"),
            SpotifyListeningImportBatch(
                id="spotify-batch-delete",
                user_id=user_id,
                source_paths=["spotify.json"],
                status="completed",
            ),
            SpotifyArtistStats(
                stat_key="spotify-artist-delete",
                user_id=user_id,
                normalized_artist_name="artist",
                artist_name="Artist",
                play_count=1,
                meaningful_play_count=1,
                skipped_count=0,
                total_ms_played=180000,
                first_played_at=now,
                last_played_at=now,
            ),
            session_group,
            listening_session,
            SessionTracks(session_id=listening_session.id, track_position="A1", track_title="Track"),
            SessionsMoods(name="Late Night", user_id=user_id, is_custom=True),
        ]
    )
    db_session.flush()
    db_session.add(
        ReleaseCollectionFolder(
            user_id=user_id,
            release_id="release-delete",
            collection_folder_id=folder.id,
            discogs_instance_id=123,
        )
    )
    db_session.commit()


def _service(
    *,
    repository: AuthRepository,
    clock: AuthTestClock,
    email_sender: AuthEmailSender,
    password_reset_code_ttl: timedelta = timedelta(minutes=15),
    code_failed_attempt_limit: int = 5,
    code_failed_attempt_lock: timedelta = timedelta(minutes=5),
) -> AuthAccountService:
    return AuthAccountService(
        repository=repository,
        password_hasher=Argon2idPasswordHasher(FAST_HASH_CONFIG),
        email_sender=email_sender,
        code_hash_secret="test-code-secret",
        now_provider=clock.now,
        verification_code_ttl=timedelta(minutes=15),
        password_reset_code_ttl=password_reset_code_ttl,
        resend_cooldown=timedelta(seconds=60),
        code_failed_attempt_limit=code_failed_attempt_limit,
        code_failed_attempt_lock=code_failed_attempt_lock,
    )
