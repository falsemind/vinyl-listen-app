import base64
import hashlib
import hmac
import json
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.auth import AuthSession
from app.repositories.auth_repository import AuthRepository

ACCESS_TOKEN_VERSION = "v1"
ACCESS_TOKEN_ALGORITHM = "HS256"
REFRESH_TOKEN_BYTES = 48


class AuthTokenConfigurationError(Exception):
    pass


class AccessTokenError(Exception):
    pass


class AccessTokenExpiredError(AccessTokenError):
    pass


class InvalidAccessTokenError(AccessTokenError):
    pass


class RefreshTokenError(Exception):
    pass


class RefreshTokenInvalidError(RefreshTokenError):
    pass


class RefreshTokenExpiredError(RefreshTokenError):
    pass


class RefreshTokenRevokedError(RefreshTokenError):
    pass


class RefreshTokenReuseDetectedError(RefreshTokenError):
    pass


class InactivityReauthRequiredError(RefreshTokenError):
    pass


@dataclass(frozen=True)
class AccessTokenClaims:
    user_id: str
    session_id: str
    issued_at: datetime
    expires_at: datetime


@dataclass(frozen=True)
class TokenPair:
    access_token: str
    access_expires_at: datetime
    refresh_token: str
    refresh_expires_at: datetime
    session_id: str


class AccessTokenService:
    """Issue and verify short-lived signed access tokens."""

    def __init__(
        self,
        *,
        secret: str,
        lifetime: timedelta | None = None,
    ) -> None:
        lifetime = lifetime or timedelta(seconds=settings.auth_access_token_lifetime_seconds)
        if not secret.strip():
            raise AuthTokenConfigurationError("auth access token secret must be configured.")
        if lifetime <= timedelta(0):
            raise ValueError("access token lifetime must be positive.")

        self._secret = secret.encode("utf-8")
        self._lifetime = lifetime

    @classmethod
    def from_settings(cls) -> "AccessTokenService":
        if settings.auth_access_token_secret is None:
            raise AuthTokenConfigurationError("AUTH_ACCESS_TOKEN_SECRET is required.")
        return cls(secret=settings.auth_access_token_secret)

    def issue(self, *, user_id: str, session_id: str, now: datetime | None = None) -> tuple[str, datetime]:
        issued_at = now or datetime.now(UTC)
        expires_at = issued_at + self._lifetime
        header = {"alg": ACCESS_TOKEN_ALGORITHM, "typ": "JWT", "v": ACCESS_TOKEN_VERSION}
        payload = {
            "sub": user_id,
            "sid": session_id,
            "iat": int(issued_at.timestamp()),
            "exp": int(expires_at.timestamp()),
        }
        signing_input = f"{_b64_json(header)}.{_b64_json(payload)}"
        signature = _b64_bytes(_hmac_sha256(self._secret, signing_input.encode("utf-8")))
        return f"{signing_input}.{signature}", expires_at

    def verify(self, token: str, *, now: datetime | None = None) -> AccessTokenClaims:
        parts = token.split(".")
        if len(parts) != 3:
            raise InvalidAccessTokenError("access token must have three segments.")

        signing_input = f"{parts[0]}.{parts[1]}"
        expected_signature = _b64_bytes(_hmac_sha256(self._secret, signing_input.encode("utf-8")))
        if not hmac.compare_digest(expected_signature, parts[2]):
            raise InvalidAccessTokenError("access token signature is invalid.")

        header = _decode_json(parts[0])
        payload = _decode_json(parts[1])
        if header.get("alg") != ACCESS_TOKEN_ALGORITHM or header.get("v") != ACCESS_TOKEN_VERSION:
            raise InvalidAccessTokenError("access token header is invalid.")

        user_id = payload.get("sub")
        session_id = payload.get("sid")
        issued_at = _timestamp_claim(payload, "iat")
        expires_at = _timestamp_claim(payload, "exp")
        if not isinstance(user_id, str) or not isinstance(session_id, str):
            raise InvalidAccessTokenError("access token subject is invalid.")

        current_time = now or datetime.now(UTC)
        if expires_at <= current_time:
            raise AccessTokenExpiredError("access token is expired.")

        return AccessTokenClaims(
            user_id=user_id,
            session_id=session_id,
            issued_at=issued_at,
            expires_at=expires_at,
        )


class AuthTokenLifecycleService:
    """Create and refresh auth sessions with refresh-token rotation."""

    def __init__(
        self,
        *,
        repository: AuthRepository | None = None,
        access_token_service: AccessTokenService | None = None,
        now_provider: Callable[[], datetime] | None = None,
        refresh_token_lifetime: timedelta | None = None,
        inactivity_window: timedelta | None = None,
    ) -> None:
        refresh_token_lifetime = refresh_token_lifetime or timedelta(days=settings.auth_refresh_token_lifetime_days)
        inactivity_window = inactivity_window or timedelta(days=settings.auth_inactivity_reauth_days)
        if refresh_token_lifetime <= timedelta(0):
            raise ValueError("refresh token lifetime must be positive.")
        if inactivity_window <= timedelta(0):
            raise ValueError("inactivity window must be positive.")

        self._repository = repository or AuthRepository()
        self._access_token_service = access_token_service or AccessTokenService.from_settings()
        self._now_provider = now_provider or (lambda: datetime.now(UTC))
        self._refresh_token_lifetime = refresh_token_lifetime
        self._inactivity_window = inactivity_window

    def create_session(
        self,
        db: Session,
        *,
        user_id: str,
        device_label: str | None = None,
    ) -> TokenPair:
        now = self._now_provider()
        refresh_token = generate_refresh_token()
        refresh_expires_at = now + self._refresh_token_lifetime
        auth_session = self._repository.create_auth_session(
            db,
            user_id=user_id,
            refresh_token_hash=hash_refresh_token(refresh_token),
            last_activity_at=now,
            expires_at=refresh_expires_at,
            device_label=device_label,
        )
        access_token, access_expires_at = self._access_token_service.issue(
            user_id=user_id,
            session_id=auth_session.id,
            now=now,
        )
        return TokenPair(
            access_token=access_token,
            access_expires_at=access_expires_at,
            refresh_token=refresh_token,
            refresh_expires_at=refresh_expires_at,
            session_id=auth_session.id,
        )

    def refresh_session(self, db: Session, *, refresh_token: str) -> TokenPair:
        now = self._now_provider()
        refresh_token_hash = hash_refresh_token(refresh_token)
        auth_session = self._repository.get_auth_session_by_refresh_token_hash(db, refresh_token_hash)
        if auth_session is None:
            self._handle_missing_refresh_token(db, refresh_token_hash=refresh_token_hash, now=now)

        assert auth_session is not None
        self._validate_refreshable_session(db, auth_session=auth_session, now=now)

        next_refresh_token = generate_refresh_token()
        next_refresh_expires_at = now + self._refresh_token_lifetime
        self._repository.create_consumed_refresh_token(
            db,
            session_id=auth_session.id,
            user_id=auth_session.user_id,
            refresh_token_hash=refresh_token_hash,
            consumed_at=now,
            expires_at=auth_session.expires_at,
            commit=False,
        )
        self._repository.touch_auth_session(
            db,
            auth_session=auth_session,
            last_activity_at=now,
            refresh_token_hash=hash_refresh_token(next_refresh_token),
            expires_at=next_refresh_expires_at,
            commit=False,
        )
        db.commit()
        db.refresh(auth_session)

        access_token, access_expires_at = self._access_token_service.issue(
            user_id=auth_session.user_id,
            session_id=auth_session.id,
            now=now,
        )
        return TokenPair(
            access_token=access_token,
            access_expires_at=access_expires_at,
            refresh_token=next_refresh_token,
            refresh_expires_at=next_refresh_expires_at,
            session_id=auth_session.id,
        )

    def _handle_missing_refresh_token(self, db: Session, *, refresh_token_hash: str, now: datetime) -> None:
        consumed_token = self._repository.get_consumed_refresh_token_by_hash(db, refresh_token_hash)
        if consumed_token is None:
            raise RefreshTokenInvalidError("refresh token is invalid.")

        auth_session = self._repository.get_auth_session_by_id(db, consumed_token.session_id)
        if auth_session is not None and auth_session.revoked_at is None:
            self._repository.revoke_auth_session(
                db,
                auth_session=auth_session,
                revoked_at=now,
                reason="refresh_token_reuse",
            )
        raise RefreshTokenReuseDetectedError("refresh token reuse detected.")

    def _validate_refreshable_session(self, db: Session, *, auth_session: AuthSession, now: datetime) -> None:
        if auth_session.revoked_at is not None:
            raise RefreshTokenRevokedError("refresh token session is revoked.")

        if _ensure_utc(auth_session.expires_at) <= now:
            self._repository.revoke_auth_session(
                db,
                auth_session=auth_session,
                revoked_at=now,
                reason="refresh_token_expired",
            )
            raise RefreshTokenExpiredError("refresh token is expired.")

        if _ensure_utc(auth_session.last_activity_at) <= now - self._inactivity_window:
            self._repository.revoke_auth_session(
                db,
                auth_session=auth_session,
                revoked_at=now,
                reason="inactivity_reauth_required",
            )
            raise InactivityReauthRequiredError("password re-entry is required after inactivity.")


def generate_refresh_token() -> str:
    return secrets.token_urlsafe(REFRESH_TOKEN_BYTES)


def hash_refresh_token(refresh_token: str) -> str:
    return hashlib.sha256(refresh_token.encode("utf-8")).hexdigest()


def _b64_json(value: dict[str, Any]) -> str:
    return _b64_bytes(json.dumps(value, separators=(",", ":"), sort_keys=True).encode("utf-8"))


def _b64_bytes(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _decode_json(value: str) -> dict[str, Any]:
    try:
        decoded = base64.urlsafe_b64decode(_restore_padding(value)).decode("utf-8")
        parsed = json.loads(decoded)
    except (ValueError, json.JSONDecodeError) as exc:
        raise InvalidAccessTokenError("access token segment is invalid.") from exc
    if not isinstance(parsed, dict):
        raise InvalidAccessTokenError("access token segment must be an object.")
    return parsed


def _restore_padding(value: str) -> str:
    return value + ("=" * (-len(value) % 4))


def _hmac_sha256(secret: bytes, value: bytes) -> bytes:
    return hmac.new(secret, value, hashlib.sha256).digest()


def _timestamp_claim(payload: dict[str, Any], key: str) -> datetime:
    value = payload.get(key)
    if not isinstance(value, int):
        raise InvalidAccessTokenError(f"access token {key} claim is invalid.")
    return datetime.fromtimestamp(value, UTC)


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
