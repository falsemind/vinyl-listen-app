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
from app.services.auth_token_service import (
    AccessTokenExpiredError,
    AccessTokenService,
    AuthTokenLifecycleService,
    InactivityReauthRequiredError,
    InvalidAccessTokenError,
    RefreshTokenExpiredError,
    RefreshTokenReuseDetectedError,
    hash_refresh_token,
)

AUTH_TABLES = [
    UserAccount.__table__,
    AuthSession.__table__,
    ConsumedRefreshToken.__table__,
    EmailVerificationCode.__table__,
    PasswordResetCode.__table__,
    UserEntitlement.__table__,
    UsageEvent.__table__,
]


class AuthTestClock:
    def __init__(self, value: datetime) -> None:
        self.value = value

    def now(self) -> datetime:
        return self.value

    def advance(self, delta: timedelta) -> None:
        self.value += delta


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


def test_access_token_service_issues_and_verifies_minimal_claims(clock: AuthTestClock) -> None:
    service = AccessTokenService(secret="test-secret", lifetime=timedelta(minutes=15))

    token, expires_at = service.issue(user_id="user-1", session_id="session-1", now=clock.now())
    claims = service.verify(token, now=clock.now())

    assert claims.user_id == "user-1"
    assert claims.session_id == "session-1"
    assert claims.issued_at == clock.now()
    assert claims.expires_at == expires_at


def test_access_token_service_rejects_expired_and_tampered_tokens(clock: AuthTestClock) -> None:
    service = AccessTokenService(secret="test-secret", lifetime=timedelta(minutes=15))
    token, _ = service.issue(user_id="user-1", session_id="session-1", now=clock.now())

    with pytest.raises(AccessTokenExpiredError):
        service.verify(token, now=clock.now() + timedelta(minutes=16))

    tampered = f"{token[:-1]}x"
    with pytest.raises(InvalidAccessTokenError):
        service.verify(tampered, now=clock.now())


def test_create_session_persists_hashed_refresh_token_and_access_token(
    db_session: Session,
    repository: AuthRepository,
    clock: AuthTestClock,
) -> None:
    _create_user(db_session, repository)
    lifecycle = _lifecycle(repository=repository, clock=clock)

    token_pair = lifecycle.create_session(db_session, user_id="user-1", device_label="Pixel")

    auth_session = repository.get_auth_session_by_refresh_token_hash(
        db_session,
        hash_refresh_token(token_pair.refresh_token),
    )
    assert auth_session is not None
    assert auth_session.user_id == "user-1"
    assert auth_session.device_label == "Pixel"
    assert auth_session.expires_at == _sqlite_datetime(token_pair.refresh_expires_at)

    claims = _access_service().verify(token_pair.access_token, now=clock.now())
    assert claims.user_id == "user-1"
    assert claims.session_id == token_pair.session_id


def test_refresh_session_rotates_refresh_token_and_records_consumed_hash(
    db_session: Session,
    repository: AuthRepository,
    clock: AuthTestClock,
) -> None:
    _create_user(db_session, repository)
    lifecycle = _lifecycle(repository=repository, clock=clock)
    first_pair = lifecycle.create_session(db_session, user_id="user-1")
    clock.advance(timedelta(minutes=5))

    second_pair = lifecycle.refresh_session(db_session, refresh_token=first_pair.refresh_token)

    assert second_pair.refresh_token != first_pair.refresh_token
    assert (
        repository.get_auth_session_by_refresh_token_hash(
            db_session,
            hash_refresh_token(first_pair.refresh_token),
        )
        is None
    )
    assert (
        repository.get_auth_session_by_refresh_token_hash(
            db_session,
            hash_refresh_token(second_pair.refresh_token),
        )
        is not None
    )
    assert (
        repository.get_consumed_refresh_token_by_hash(
            db_session,
            hash_refresh_token(first_pair.refresh_token),
        )
        is not None
    )


def test_reusing_consumed_refresh_token_revokes_session(
    db_session: Session,
    repository: AuthRepository,
    clock: AuthTestClock,
) -> None:
    _create_user(db_session, repository)
    lifecycle = _lifecycle(repository=repository, clock=clock)
    first_pair = lifecycle.create_session(db_session, user_id="user-1")
    second_pair = lifecycle.refresh_session(db_session, refresh_token=first_pair.refresh_token)
    clock.advance(timedelta(minutes=1))

    with pytest.raises(RefreshTokenReuseDetectedError):
        lifecycle.refresh_session(db_session, refresh_token=first_pair.refresh_token)

    auth_session = repository.get_auth_session_by_refresh_token_hash(
        db_session,
        hash_refresh_token(second_pair.refresh_token),
    )
    assert auth_session is not None
    assert auth_session.revoked_at == _sqlite_datetime(clock.now())
    assert auth_session.revoke_reason == "refresh_token_reuse"


def test_duplicate_consumed_hash_during_refresh_is_treated_as_reuse(
    db_session: Session,
    repository: AuthRepository,
    clock: AuthTestClock,
) -> None:
    _create_user(db_session, repository)
    lifecycle = _lifecycle(repository=repository, clock=clock)
    token_pair = lifecycle.create_session(db_session, user_id="user-1")
    refresh_token_hash = hash_refresh_token(token_pair.refresh_token)
    auth_session = repository.get_auth_session_by_refresh_token_hash(db_session, refresh_token_hash)
    assert auth_session is not None
    repository.create_consumed_refresh_token(
        db_session,
        session_id=auth_session.id,
        user_id=auth_session.user_id,
        refresh_token_hash=refresh_token_hash,
        consumed_at=clock.now(),
        expires_at=auth_session.expires_at,
    )
    clock.advance(timedelta(minutes=1))

    with pytest.raises(RefreshTokenReuseDetectedError):
        lifecycle.refresh_session(db_session, refresh_token=token_pair.refresh_token)

    revoked_session = repository.get_auth_session_by_refresh_token_hash(db_session, refresh_token_hash)
    assert revoked_session is not None
    assert revoked_session.revoked_at == _sqlite_datetime(clock.now())
    assert revoked_session.revoke_reason == "refresh_token_reuse"


def test_refresh_requires_reauth_after_inactivity(
    db_session: Session,
    repository: AuthRepository,
    clock: AuthTestClock,
) -> None:
    _create_user(db_session, repository)
    lifecycle = _lifecycle(repository=repository, clock=clock)
    token_pair = lifecycle.create_session(db_session, user_id="user-1")
    clock.advance(timedelta(days=8))

    with pytest.raises(InactivityReauthRequiredError):
        lifecycle.refresh_session(db_session, refresh_token=token_pair.refresh_token)

    auth_session = repository.get_auth_session_by_refresh_token_hash(
        db_session,
        hash_refresh_token(token_pair.refresh_token),
    )
    assert auth_session is not None
    assert auth_session.revoked_at == _sqlite_datetime(clock.now())
    assert auth_session.revoke_reason == "inactivity_reauth_required"


def test_refresh_rejects_expired_refresh_token(
    db_session: Session,
    repository: AuthRepository,
    clock: AuthTestClock,
) -> None:
    _create_user(db_session, repository)
    lifecycle = _lifecycle(
        repository=repository,
        clock=clock,
        refresh_token_lifetime=timedelta(days=1),
        inactivity_window=timedelta(days=7),
    )
    token_pair = lifecycle.create_session(db_session, user_id="user-1")
    clock.advance(timedelta(days=2))

    with pytest.raises(RefreshTokenExpiredError):
        lifecycle.refresh_session(db_session, refresh_token=token_pair.refresh_token)

    auth_session = repository.get_auth_session_by_refresh_token_hash(
        db_session,
        hash_refresh_token(token_pair.refresh_token),
    )
    assert auth_session is not None
    assert auth_session.revoked_at == _sqlite_datetime(clock.now())
    assert auth_session.revoke_reason == "refresh_token_expired"


def _create_user(db_session: Session, repository: AuthRepository) -> None:
    repository.create_user_account(
        db_session,
        user_id="user-1",
        email="alex@example.com",
        password_hash="hash",
        password_hash_algorithm="argon2id",
    )


def _access_service() -> AccessTokenService:
    return AccessTokenService(secret="test-secret", lifetime=timedelta(minutes=15))


def _lifecycle(
    *,
    repository: AuthRepository,
    clock: AuthTestClock,
    refresh_token_lifetime: timedelta = timedelta(days=30),
    inactivity_window: timedelta = timedelta(days=7),
) -> AuthTokenLifecycleService:
    return AuthTokenLifecycleService(
        repository=repository,
        access_token_service=_access_service(),
        now_provider=clock.now,
        refresh_token_lifetime=refresh_token_lifetime,
        inactivity_window=inactivity_window,
    )


def _sqlite_datetime(value: datetime) -> datetime:
    return value.replace(tzinfo=None)
