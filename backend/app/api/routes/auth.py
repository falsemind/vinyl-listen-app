from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.auth_dependencies import (
    AuthenticatedUser,
    get_auth_repository,
    raise_auth_error,
    require_authenticated_user,
)
from app.database.session import get_db
from app.repositories.auth_repository import AuthRepository
from app.schemas.auth import (
    AuthErrorResponse,
    DeleteAccountDataRequest,
    DeleteAccountDataResponse,
    DeleteAccountRequest,
    DeleteAccountResponse,
    LoginRequest,
    LogoutAllResponse,
    LogoutResponse,
    PasswordChangeRequest,
    PasswordChangeResponse,
    PasswordResetConfirmCurrentRequest,
    PasswordResetConfirmRequest,
    PasswordResetRequestRequest,
    PasswordResetRequestResponse,
    RefreshTokenRequest,
    RegisterAccountRequest,
    RegisterAccountResponse,
    ResendVerificationRequest,
    ResendVerificationResponse,
    TokenPairResponse,
    UserAccountResponse,
    VerifyEmailRequest,
)
from app.services.auth_account_service import (
    AccountDataResetInvalidPasswordError,
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
    PasswordResetCodeExpiredError,
    PasswordResetCodeInvalidError,
    PasswordResetRequestRateLimitedError,
    SignInEmailNotVerifiedError,
    SignInInvalidCredentialsError,
)
from app.services.auth_token_service import (
    AuthTokenLifecycleService,
    InactivityReauthRequiredError,
    RefreshTokenExpiredError,
    RefreshTokenInvalidError,
    RefreshTokenReuseDetectedError,
    RefreshTokenRevokedError,
    TokenPair,
)

router = APIRouter()
AUTH_AUDIT_LOGOUT = "logout"
AUTH_AUDIT_LOGOUT_ALL = "logout_all"


def get_auth_account_service() -> AuthAccountService:
    return AuthAccountService()


def get_auth_token_lifecycle_service() -> AuthTokenLifecycleService:
    return AuthTokenLifecycleService()


@router.post(
    "/register",
    response_model=RegisterAccountResponse,
    status_code=status.HTTP_201_CREATED,
    responses={409: {"model": AuthErrorResponse}},
)
def register_account(
    payload: RegisterAccountRequest,
    db: Annotated[Session, Depends(get_db)],
    account_service: Annotated[AuthAccountService, Depends(get_auth_account_service)],
) -> RegisterAccountResponse:
    try:
        result = account_service.register_account(db, email=payload.email, password=payload.password)
    except EmailAlreadyRegisteredError:
        raise_auth_error(
            status_code=status.HTTP_409_CONFLICT,
            code="email_already_registered",
            message="Email is already registered.",
        )

    return RegisterAccountResponse(
        user_id=result.user_id,
        email=result.email,
        verification_expires_at=result.verification_expires_at,
    )


@router.post(
    "/verify-email",
    response_model=UserAccountResponse,
    responses={
        400: {"model": AuthErrorResponse},
        429: {"model": AuthErrorResponse},
        410: {"model": AuthErrorResponse},
    },
)
def verify_email(
    payload: VerifyEmailRequest,
    db: Annotated[Session, Depends(get_db)],
    account_service: Annotated[AuthAccountService, Depends(get_auth_account_service)],
) -> UserAccountResponse:
    try:
        user = account_service.verify_email(db, email=payload.email, code=payload.code)
    except EmailVerificationCodeExpiredError:
        raise_auth_error(status_code=status.HTTP_410_GONE, code="email_code_expired", message="Code has expired.")
    except EmailVerificationCodeConsumedError:
        raise_auth_error(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="email_code_consumed",
            message="Code has already been used.",
        )
    except EmailVerificationAttemptRateLimitedError:
        raise_auth_error(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            code="email_code_attempts_rate_limited",
            message="Email verification attempts are rate limited.",
        )
    except EmailVerificationCodeInvalidError:
        raise_auth_error(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="email_code_invalid",
            message="Code is invalid.",
        )

    return _account_response(user_id=user.id, email=user.email, email_verified_at=user.email_verified_at)


@router.post(
    "/resend-verification",
    response_model=ResendVerificationResponse,
    responses={400: {"model": AuthErrorResponse}, 429: {"model": AuthErrorResponse}},
)
def resend_verification(
    payload: ResendVerificationRequest,
    db: Annotated[Session, Depends(get_db)],
    account_service: Annotated[AuthAccountService, Depends(get_auth_account_service)],
) -> ResendVerificationResponse:
    try:
        result = account_service.resend_email_verification(db, email=payload.email)
    except EmailVerificationResendRateLimitedError:
        raise_auth_error(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            code="email_verification_rate_limited",
            message="Email verification resend is rate limited.",
        )
    except EmailVerificationCodeInvalidError:
        raise_auth_error(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="email_code_invalid",
            message="Code is invalid.",
        )

    return ResendVerificationResponse(
        user_id=result.user_id,
        email=result.email,
        verification_expires_at=result.verification_expires_at,
        resend_count=result.resend_count,
    )


@router.post(
    "/login",
    response_model=TokenPairResponse,
    responses={401: {"model": AuthErrorResponse}, 403: {"model": AuthErrorResponse}},
)
def login(
    payload: LoginRequest,
    db: Annotated[Session, Depends(get_db)],
    account_service: Annotated[AuthAccountService, Depends(get_auth_account_service)],
    token_service: Annotated[AuthTokenLifecycleService, Depends(get_auth_token_lifecycle_service)],
) -> TokenPairResponse:
    try:
        result = account_service.sign_in_with_password(db, email=payload.email, password=payload.password)
    except SignInEmailNotVerifiedError:
        raise_auth_error(
            status_code=status.HTTP_403_FORBIDDEN,
            code="email_not_verified",
            message="Email must be verified before signing in.",
        )
    except SignInInvalidCredentialsError:
        raise_auth_error(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="invalid_credentials",
            message="Email or password is invalid.",
        )

    return _token_pair_response(
        token_service.create_session(db, user_id=result.user.id, device_label=payload.device_label)
    )


@router.post(
    "/refresh",
    response_model=TokenPairResponse,
    responses={401: {"model": AuthErrorResponse}},
)
def refresh(
    payload: RefreshTokenRequest,
    db: Annotated[Session, Depends(get_db)],
    token_service: Annotated[AuthTokenLifecycleService, Depends(get_auth_token_lifecycle_service)],
) -> TokenPairResponse:
    try:
        token_pair = token_service.refresh_session(db, refresh_token=payload.refresh_token)
    except RefreshTokenReuseDetectedError:
        raise_auth_error(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="refresh_token_reuse_detected",
            message="Refresh token reuse was detected.",
        )
    except InactivityReauthRequiredError:
        raise_auth_error(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="inactivity_reauth_required",
            message="Password re-entry is required after inactivity.",
        )
    except RefreshTokenExpiredError:
        raise_auth_error(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="refresh_token_expired",
            message="Refresh token has expired.",
        )
    except RefreshTokenRevokedError:
        raise_auth_error(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="refresh_token_revoked",
            message="Refresh token is revoked.",
        )
    except RefreshTokenInvalidError:
        raise_auth_error(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="invalid_refresh_token",
            message="Refresh token is invalid.",
        )

    return _token_pair_response(token_pair)


@router.post(
    "/logout",
    response_model=LogoutResponse,
)
def logout(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    repository: Annotated[AuthRepository, Depends(get_auth_repository)],
) -> LogoutResponse:
    auth_session = repository.get_auth_session_by_id(db, current_user.claims.session_id)
    if auth_session is not None and auth_session.revoked_at is None:
        now = datetime.now(UTC)
        repository.revoke_auth_session(
            db,
            auth_session=auth_session,
            revoked_at=now,
            reason="logout",
            commit=False,
        )
        repository.record_auth_audit_event(
            db,
            user_id=current_user.account.id,
            session_id=current_user.claims.session_id,
            event_type=AUTH_AUDIT_LOGOUT,
            outcome="success",
            occurred_at=now,
            commit=False,
        )
        db.commit()
    return LogoutResponse(revoked=True)


@router.post(
    "/logout-all",
    response_model=LogoutAllResponse,
)
def logout_all(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    repository: Annotated[AuthRepository, Depends(get_auth_repository)],
) -> LogoutAllResponse:
    now = datetime.now(UTC)
    revoked_sessions = repository.revoke_user_sessions(
        db,
        user_id=current_user.account.id,
        revoked_at=now,
        reason="logout_all",
        commit=False,
    )
    repository.record_auth_audit_event(
        db,
        user_id=current_user.account.id,
        session_id=current_user.claims.session_id,
        event_type=AUTH_AUDIT_LOGOUT_ALL,
        outcome="success",
        occurred_at=now,
        event_details={"revoked_sessions": revoked_sessions},
        commit=False,
    )
    db.commit()
    return LogoutAllResponse(revoked_sessions=revoked_sessions)


@router.get(
    "/me",
    response_model=UserAccountResponse,
)
def me(current_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)]) -> UserAccountResponse:
    return _account_response(
        user_id=current_user.account.id,
        email=current_user.account.email,
        email_verified_at=current_user.account.email_verified_at,
    )


@router.post(
    "/password-reset/request",
    response_model=PasswordResetRequestResponse,
    responses={429: {"model": AuthErrorResponse}},
)
def request_password_reset(
    payload: PasswordResetRequestRequest,
    db: Annotated[Session, Depends(get_db)],
    account_service: Annotated[AuthAccountService, Depends(get_auth_account_service)],
) -> PasswordResetRequestResponse:
    try:
        result = account_service.request_password_reset(db, email=payload.email)
    except PasswordResetRequestRateLimitedError:
        raise_auth_error(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            code="password_reset_rate_limited",
            message="Password reset request is rate limited.",
        )

    return PasswordResetRequestResponse(accepted=result.accepted, email=result.email)


@router.post(
    "/password-reset/request-current",
    response_model=PasswordResetRequestResponse,
    responses={429: {"model": AuthErrorResponse}},
)
def request_current_user_password_reset(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    account_service: Annotated[AuthAccountService, Depends(get_auth_account_service)],
) -> PasswordResetRequestResponse:
    try:
        result = account_service.request_password_reset(db, email=current_user.account.email)
    except PasswordResetRequestRateLimitedError:
        raise_auth_error(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            code="password_reset_rate_limited",
            message="Password reset request is rate limited.",
        )

    return PasswordResetRequestResponse(accepted=result.accepted, email=result.email)


@router.post(
    "/password-reset/confirm",
    response_model=UserAccountResponse,
    responses={400: {"model": AuthErrorResponse}, 410: {"model": AuthErrorResponse}, 429: {"model": AuthErrorResponse}},
)
def confirm_password_reset(
    payload: PasswordResetConfirmRequest,
    db: Annotated[Session, Depends(get_db)],
    account_service: Annotated[AuthAccountService, Depends(get_auth_account_service)],
) -> UserAccountResponse:
    try:
        user = account_service.confirm_password_reset(
            db,
            email=payload.email,
            code=payload.code,
            new_password=payload.new_password,
        )
    except PasswordResetCodeExpiredError:
        raise_auth_error(status_code=status.HTTP_410_GONE, code="password_reset_expired", message="Code has expired.")
    except PasswordResetCodeConsumedError:
        raise_auth_error(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="password_reset_consumed",
            message="Code has already been used.",
        )
    except PasswordResetAttemptRateLimitedError:
        raise_auth_error(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            code="password_reset_attempts_rate_limited",
            message="Password reset attempts are rate limited.",
        )
    except PasswordResetCodeInvalidError:
        raise_auth_error(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="password_reset_invalid",
            message="Code is invalid.",
        )

    return _account_response(user_id=user.id, email=user.email, email_verified_at=user.email_verified_at)


@router.post(
    "/password-reset/confirm-current",
    response_model=UserAccountResponse,
    responses={400: {"model": AuthErrorResponse}, 410: {"model": AuthErrorResponse}, 429: {"model": AuthErrorResponse}},
)
def confirm_current_user_password_reset(
    payload: PasswordResetConfirmCurrentRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    account_service: Annotated[AuthAccountService, Depends(get_auth_account_service)],
) -> UserAccountResponse:
    try:
        user = account_service.confirm_password_reset(
            db,
            email=current_user.account.email,
            code=payload.code,
            new_password=payload.new_password,
        )
    except PasswordResetCodeExpiredError:
        raise_auth_error(status_code=status.HTTP_410_GONE, code="password_reset_expired", message="Code has expired.")
    except PasswordResetCodeConsumedError:
        raise_auth_error(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="password_reset_consumed",
            message="Code has already been used.",
        )
    except PasswordResetAttemptRateLimitedError:
        raise_auth_error(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            code="password_reset_attempts_rate_limited",
            message="Password reset attempts are rate limited.",
        )
    except PasswordResetCodeInvalidError:
        raise_auth_error(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="password_reset_invalid",
            message="Code is invalid.",
        )

    return _account_response(user_id=user.id, email=user.email, email_verified_at=user.email_verified_at)


@router.post(
    "/password/change",
    response_model=PasswordChangeResponse,
    responses={401: {"model": AuthErrorResponse}},
)
def change_password(
    payload: PasswordChangeRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    account_service: Annotated[AuthAccountService, Depends(get_auth_account_service)],
) -> PasswordChangeResponse:
    try:
        result = account_service.change_password(
            db,
            user=current_user.account,
            current_password=payload.current_password,
            new_password=payload.new_password,
            current_session_id=current_user.claims.session_id,
            sign_out_everywhere=payload.sign_out_everywhere,
        )
    except PasswordChangeInvalidCurrentPasswordError:
        raise_auth_error(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="invalid_current_password",
            message="Current password is invalid.",
        )

    return PasswordChangeResponse(changed=True, revoked_sessions=result.revoked_sessions)


@router.delete(
    "/account",
    response_model=DeleteAccountResponse,
    responses={401: {"model": AuthErrorResponse}},
)
def delete_account(
    payload: DeleteAccountRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    account_service: Annotated[AuthAccountService, Depends(get_auth_account_service)],
) -> DeleteAccountResponse:
    try:
        result = account_service.delete_account(
            db,
            user=current_user.account,
            password=payload.password,
        )
    except DeleteAccountInvalidPasswordError:
        raise_auth_error(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="invalid_credentials",
            message="Password is invalid.",
        )

    return DeleteAccountResponse(
        deleted=True,
        deletion_receipt_id=result.deletion_receipt_id,
        deleted_at=result.deleted_at,
    )


@router.delete(
    "/account/data",
    response_model=DeleteAccountDataResponse,
    responses={401: {"model": AuthErrorResponse}},
)
def delete_account_data(
    payload: DeleteAccountDataRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    account_service: Annotated[AuthAccountService, Depends(get_auth_account_service)],
) -> DeleteAccountDataResponse:
    try:
        result = account_service.reset_account_data(
            db,
            user=current_user.account,
            password=payload.password,
        )
    except AccountDataResetInvalidPasswordError:
        raise_auth_error(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="invalid_credentials",
            message="Password is invalid.",
        )

    return DeleteAccountDataResponse(
        reset=True,
        reset_receipt_id=result.reset_receipt_id,
        reset_at=result.reset_at,
    )


def _account_response(*, user_id: str, email: str, email_verified_at) -> UserAccountResponse:
    return UserAccountResponse(user_id=user_id, email=email, email_verified_at=email_verified_at)


def _token_pair_response(token_pair: TokenPair) -> TokenPairResponse:
    return TokenPairResponse(
        access_token=token_pair.access_token,
        access_expires_at=token_pair.access_expires_at,
        refresh_token=token_pair.refresh_token,
        refresh_expires_at=token_pair.refresh_expires_at,
        session_id=token_pair.session_id,
    )
