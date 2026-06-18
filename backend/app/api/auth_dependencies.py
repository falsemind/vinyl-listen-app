from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.auth import UserAccount
from app.repositories.auth_repository import AuthRepository
from app.services.auth_token_service import (
    AccessTokenClaims,
    AccessTokenExpiredError,
    AccessTokenService,
    InvalidAccessTokenError,
)

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class AuthenticatedUser:
    account: UserAccount
    claims: AccessTokenClaims


class AuthAPIError(Exception):
    def __init__(self, *, status_code: int, code: str, message: str) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message


def get_auth_repository() -> AuthRepository:
    return AuthRepository()


def get_access_token_service() -> AccessTokenService:
    return AccessTokenService.from_settings()


def require_authenticated_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[Session, Depends(get_db)],
    access_token_service: Annotated[AccessTokenService, Depends(get_access_token_service)],
    repository: Annotated[AuthRepository, Depends(get_auth_repository)],
) -> AuthenticatedUser:
    if credentials is None:
        raise_auth_error(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="auth_required",
            message="Authentication is required.",
        )
    if credentials.scheme.lower() != "bearer":
        raise_auth_error(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="invalid_auth_scheme",
            message="Bearer authentication is required.",
        )

    try:
        claims = access_token_service.verify(credentials.credentials)
    except AccessTokenExpiredError:
        raise_auth_error(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="expired_access_token",
            message="Access token has expired.",
        )
    except InvalidAccessTokenError:
        raise_auth_error(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="invalid_access_token",
            message="Access token is invalid.",
        )

    account = repository.get_user_by_id(db, claims.user_id)
    auth_session = repository.get_auth_session_by_id(db, claims.session_id)
    if (
        account is None
        or auth_session is None
        or auth_session.user_id != account.id
        or not account.is_active
        or account.deleted_at is not None
    ):
        raise_auth_error(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="invalid_access_token",
            message="Access token is invalid.",
        )
    if auth_session.revoked_at is not None:
        raise_auth_error(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="revoked_session",
            message="Auth session is revoked.",
        )

    return AuthenticatedUser(account=account, claims=claims)


def raise_auth_error(*, status_code: int, code: str, message: str) -> None:
    raise AuthAPIError(status_code=status_code, code=code, message=message)
