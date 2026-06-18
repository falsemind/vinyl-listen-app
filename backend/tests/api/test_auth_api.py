from collections.abc import Generator, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.auth_dependencies import get_access_token_service, get_auth_repository
from app.api.routes.auth import get_auth_account_service, get_auth_token_lifecycle_service
from app.database.session import get_db
from app.main import app
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
from app.services.auth_account_service import AuthAccountService
from app.services.auth_email_delivery import AuthEmailMessage
from app.services.auth_token_service import AccessTokenService, AuthTokenLifecycleService
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


class AuthApiClock:
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


@dataclass(frozen=True)
class AuthApiContext:
    client: TestClient
    clock: AuthApiClock
    email_sender: RecordingEmailSender


@pytest.fixture()
def auth_api() -> Iterator[AuthApiContext]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    for table in AUTH_TABLES:
        table.create(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    repository = AuthRepository()
    clock = AuthApiClock(datetime.now(UTC))
    email_sender = RecordingEmailSender()
    access_token_service = AccessTokenService(secret="test-access-secret", lifetime=timedelta(minutes=15))
    account_service = AuthAccountService(
        repository=repository,
        password_hasher=Argon2idPasswordHasher(FAST_HASH_CONFIG),
        email_sender=email_sender,
        code_hash_secret="test-code-secret",
        now_provider=clock.now,
        verification_code_ttl=timedelta(minutes=15),
        password_reset_code_ttl=timedelta(minutes=15),
        resend_cooldown=timedelta(seconds=60),
    )
    token_service = AuthTokenLifecycleService(
        repository=repository,
        access_token_service=access_token_service,
        now_provider=clock.now,
        refresh_token_lifetime=timedelta(days=30),
        inactivity_window=timedelta(days=7),
    )

    def override_db() -> Generator[Session]:
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_auth_repository] = lambda: repository
    app.dependency_overrides[get_access_token_service] = lambda: access_token_service
    app.dependency_overrides[get_auth_account_service] = lambda: account_service
    app.dependency_overrides[get_auth_token_lifecycle_service] = lambda: token_service
    try:
        with TestClient(app) as client:
            yield AuthApiContext(client=client, clock=clock, email_sender=email_sender)
    finally:
        app.dependency_overrides.clear()
        for table in reversed(AUTH_TABLES):
            table.drop(engine)


@pytest.mark.real_auth
def test_auth_bootstrap_and_health_are_public(auth_api: AuthApiContext) -> None:
    health_response = auth_api.client.get("/api/v1/health")
    register_response = auth_api.client.post(
        "/api/v1/auth/register",
        json={"email": "alex@example.com", "password": "old-password"},
    )

    assert health_response.status_code == 200
    assert register_response.status_code == 201
    assert len(auth_api.email_sender.messages) == 1


@pytest.mark.real_auth
def test_application_endpoints_require_valid_bearer_token(auth_api: AuthApiContext) -> None:
    missing_response = auth_api.client.get("/api/v1/collection/settings")
    invalid_response = auth_api.client.get(
        "/api/v1/collection/settings",
        headers={"Authorization": "Bearer not-a-token"},
    )

    assert missing_response.status_code == 401
    assert missing_response.json() == {"error": {"code": "auth_required", "message": "Authentication is required."}}
    assert invalid_response.status_code == 401
    assert invalid_response.json() == {"error": {"code": "invalid_access_token", "message": "Access token is invalid."}}


@pytest.mark.real_auth
def test_verify_email_rejects_wrong_expired_and_reused_codes(auth_api: AuthApiContext) -> None:
    auth_api.client.post("/api/v1/auth/register", json={"email": "alex@example.com", "password": "old-password"})
    code = auth_api.email_sender.messages[0].code

    wrong_response = auth_api.client.post(
        "/api/v1/auth/verify-email",
        json={"email": "alex@example.com", "code": "000000"},
    )
    assert wrong_response.status_code == 400
    assert wrong_response.json()["error"]["code"] == "email_code_invalid"

    auth_api.clock.advance(timedelta(minutes=16))
    expired_response = auth_api.client.post(
        "/api/v1/auth/verify-email",
        json={"email": "alex@example.com", "code": code},
    )
    assert expired_response.status_code == 410
    assert expired_response.json()["error"]["code"] == "email_code_expired"

    auth_api.client.post("/api/v1/auth/register", json={"email": "sam@example.com", "password": "old-password"})
    sam_code = auth_api.email_sender.messages[1].code
    verified_response = auth_api.client.post(
        "/api/v1/auth/verify-email",
        json={"email": "sam@example.com", "code": sam_code},
    )
    reused_response = auth_api.client.post(
        "/api/v1/auth/verify-email",
        json={"email": "sam@example.com", "code": sam_code},
    )

    assert verified_response.status_code == 200
    assert reused_response.status_code == 400
    assert reused_response.json()["error"]["code"] == "email_code_consumed"


@pytest.mark.real_auth
def test_login_refresh_and_protected_access(auth_api: AuthApiContext) -> None:
    auth_api.client.post("/api/v1/auth/register", json={"email": "alex@example.com", "password": "old-password"})
    code = auth_api.email_sender.messages[0].code
    auth_api.client.post("/api/v1/auth/verify-email", json={"email": "alex@example.com", "code": code})

    login_response = auth_api.client.post(
        "/api/v1/auth/login",
        json={"email": "alex@example.com", "password": "old-password", "device_label": "Pixel"},
    )
    token_payload = login_response.json()
    protected_response = auth_api.client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token_payload['access_token']}"},
    )
    refresh_response = auth_api.client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": token_payload["refresh_token"]},
    )

    assert login_response.status_code == 200
    assert protected_response.status_code == 200
    assert protected_response.json()["email"] == "alex@example.com"
    assert refresh_response.status_code == 200
    assert refresh_response.json()["refresh_token"] != token_payload["refresh_token"]


@pytest.mark.real_auth
def test_refresh_requires_password_after_inactivity(auth_api: AuthApiContext) -> None:
    auth_api.client.post("/api/v1/auth/register", json={"email": "alex@example.com", "password": "old-password"})
    code = auth_api.email_sender.messages[0].code
    auth_api.client.post("/api/v1/auth/verify-email", json={"email": "alex@example.com", "code": code})
    login_response = auth_api.client.post(
        "/api/v1/auth/login",
        json={"email": "alex@example.com", "password": "old-password"},
    )

    auth_api.clock.advance(timedelta(days=8))
    refresh_response = auth_api.client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": login_response.json()["refresh_token"]},
    )

    assert refresh_response.status_code == 401
    assert refresh_response.json() == {
        "error": {
            "code": "inactivity_reauth_required",
            "message": "Password re-entry is required after inactivity.",
        }
    }
