import hashlib
import hmac
import logging
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.auth import EmailVerificationCode, PasswordResetCode, UserAccount
from app.repositories.auth_repository import AuthRepository, normalize_email
from app.services.auth_email_delivery import (
    AuthEmailDeliveryError,
    AuthEmailMessage,
    AuthEmailSender,
    build_auth_email_sender,
)
from app.services.password_hashing import Argon2idPasswordHasher

EMAIL_VERIFICATION_PURPOSE = "email_verification"
PASSWORD_RESET_PURPOSE = "password_reset"
PASSWORD_CHANGE_NOTIFICATION_PURPOSE = "password_change_notification"

logger = logging.getLogger(__name__)


class AuthAccountError(Exception):
    pass


class AuthAccountConfigurationError(AuthAccountError):
    pass


class EmailAlreadyRegisteredError(AuthAccountError):
    pass


class EmailVerificationCodeInvalidError(AuthAccountError):
    pass


class EmailVerificationCodeExpiredError(AuthAccountError):
    pass


class EmailVerificationCodeConsumedError(AuthAccountError):
    pass


class EmailVerificationResendRateLimitedError(AuthAccountError):
    pass


class PasswordResetCodeInvalidError(AuthAccountError):
    pass


class PasswordResetCodeExpiredError(AuthAccountError):
    pass


class PasswordResetCodeConsumedError(AuthAccountError):
    pass


class PasswordResetRequestRateLimitedError(AuthAccountError):
    pass


class SignInInvalidCredentialsError(AuthAccountError):
    pass


class SignInEmailNotVerifiedError(AuthAccountError):
    pass


class PasswordChangeInvalidCurrentPasswordError(AuthAccountError):
    pass


class DeleteAccountInvalidPasswordError(AuthAccountError):
    pass


@dataclass(frozen=True)
class RegisterAccountResult:
    user_id: str
    email: str
    verification_expires_at: datetime


@dataclass(frozen=True)
class ResendVerificationResult:
    user_id: str
    email: str
    verification_expires_at: datetime
    resend_count: int


@dataclass(frozen=True)
class PasswordResetRequestResult:
    email: str
    accepted: bool = True


@dataclass(frozen=True)
class SignInResult:
    user: UserAccount


@dataclass(frozen=True)
class PasswordChangeResult:
    user: UserAccount
    revoked_sessions: int


@dataclass(frozen=True)
class DeleteAccountResult:
    deletion_receipt_id: str
    deleted_at: datetime


class AuthAccountService:
    """Account registration, email verification, and reset flows."""

    def __init__(
        self,
        *,
        repository: AuthRepository | None = None,
        password_hasher: Argon2idPasswordHasher | None = None,
        email_sender: AuthEmailSender | None = None,
        code_hash_secret: str | None = None,
        now_provider: Callable[[], datetime] | None = None,
        verification_code_ttl: timedelta | None = None,
        password_reset_code_ttl: timedelta | None = None,
        resend_cooldown: timedelta | None = None,
        code_length: int = settings.auth_email_code_length,
    ) -> None:
        self._repository = repository or AuthRepository()
        self._password_hasher = password_hasher or Argon2idPasswordHasher()
        self._email_sender = email_sender or build_auth_email_sender()
        self._code_hash_secret = _resolve_code_hash_secret(code_hash_secret)
        self._now_provider = now_provider or (lambda: datetime.now(UTC))
        self._verification_code_ttl = verification_code_ttl or timedelta(
            minutes=settings.auth_email_verification_code_ttl_minutes
        )
        self._password_reset_code_ttl = password_reset_code_ttl or timedelta(
            minutes=settings.auth_password_reset_code_ttl_minutes
        )
        self._resend_cooldown = resend_cooldown or timedelta(seconds=settings.auth_email_resend_cooldown_seconds)
        self._code_length = code_length

        if self._code_length <= 0:
            raise ValueError("code length must be positive.")

    def register_account(self, db: Session, *, email: str, password: str) -> RegisterAccountResult:
        existing_user = self._repository.get_user_by_normalized_email(db, email)
        if existing_user is not None:
            raise EmailAlreadyRegisteredError("email is already registered.")

        password_hash = self._password_hasher.hash_password(password)
        try:
            user = self._repository.create_user_account(
                db,
                email=email,
                password_hash=password_hash.password_hash,
                password_hash_algorithm=password_hash.algorithm,
                password_hash_version=password_hash.version,
                password_hash_params=password_hash.params,
                commit=False,
            )
            code, verification_code = self._create_email_verification_code(db, user=user, resend_count=0)
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise EmailAlreadyRegisteredError("email is already registered.") from exc

        self._send_email_verification_code(user.email, code)
        return RegisterAccountResult(
            user_id=user.id,
            email=user.email,
            verification_expires_at=verification_code.expires_at,
        )

    def verify_email(self, db: Session, *, email: str, code: str) -> UserAccount:
        verification_code = self._get_email_verification_code(db, email=email, code=code)
        now = self._now_provider()
        _ensure_code_usable(
            code=verification_code,
            now=now,
            invalid_error=EmailVerificationCodeInvalidError,
            expired_error=EmailVerificationCodeExpiredError,
            consumed_error=EmailVerificationCodeConsumedError,
        )

        user = self._repository.get_user_by_id(db, verification_code.user_id)
        if user is None or user.normalized_email != normalize_email(email):
            raise EmailVerificationCodeInvalidError("email verification code is invalid.")

        self._repository.consume_email_verification_code(db, code=verification_code, consumed_at=now, commit=False)
        self._repository.mark_email_verified(db, user=user, verified_at=now, commit=False)
        db.commit()
        db.refresh(user)
        return user

    def resend_email_verification(self, db: Session, *, email: str) -> ResendVerificationResult:
        user = self._repository.get_user_by_normalized_email(db, email)
        if user is None or user.email_verified_at is not None:
            raise EmailVerificationCodeInvalidError("email verification code is invalid.")

        now = self._now_provider()
        latest_code = self._repository.get_latest_email_verification_code(db, user_id=user.id)
        if (
            latest_code is not None
            and latest_code.rate_limited_until is not None
            and _ensure_utc(latest_code.rate_limited_until) > now
        ):
            raise EmailVerificationResendRateLimitedError("email verification resend is rate limited.")

        resend_count = 0 if latest_code is None else latest_code.resend_count + 1
        code, verification_code = self._create_email_verification_code(db, user=user, resend_count=resend_count)
        db.commit()

        self._send_email_verification_code(user.email, code)
        return ResendVerificationResult(
            user_id=user.id,
            email=user.email,
            verification_expires_at=verification_code.expires_at,
            resend_count=resend_count,
        )

    def request_password_reset(self, db: Session, *, email: str) -> PasswordResetRequestResult:
        user = self._repository.get_user_by_normalized_email(db, email)
        if user is None or user.deleted_at is not None:
            return PasswordResetRequestResult(email=email.strip())

        now = self._now_provider()
        latest_code = self._repository.get_latest_password_reset_code(db, user_id=user.id)
        if (
            latest_code is not None
            and latest_code.consumed_at is None
            and _ensure_utc(latest_code.created_at) + self._resend_cooldown > now
        ):
            raise PasswordResetRequestRateLimitedError("password reset request is rate limited.")

        self._repository.consume_unconsumed_password_reset_codes(
            db,
            user_id=user.id,
            consumed_at=now,
            commit=False,
        )
        code, reset_code = self._create_password_reset_code(db, user=user)
        db.commit()

        self._send_password_reset_code(user.email, code, reset_code.expires_at)
        return PasswordResetRequestResult(email=user.email)

    def sign_in_with_password(self, db: Session, *, email: str, password: str) -> SignInResult:
        user = self._repository.get_user_by_normalized_email(db, email)
        if user is None or user.deleted_at is not None or not user.is_active:
            raise SignInInvalidCredentialsError("email or password is invalid.")

        verification = self._password_hasher.verify_password(
            password=password,
            password_hash=user.password_hash,
            algorithm=user.password_hash_algorithm,
            version=user.password_hash_version,
            params=user.password_hash_params,
        )
        if not verification.is_valid:
            raise SignInInvalidCredentialsError("email or password is invalid.")
        if user.email_verified_at is None:
            raise SignInEmailNotVerifiedError("email must be verified before signing in.")

        if verification.needs_rehash:
            password_hash = self._password_hasher.hash_password(password)
            self._repository.update_password_hash(
                db,
                user=user,
                password_hash=password_hash.password_hash,
                password_hash_algorithm=password_hash.algorithm,
                password_hash_version=password_hash.version,
                password_hash_params=password_hash.params,
                commit=False,
            )
            db.commit()
            db.refresh(user)

        return SignInResult(user=user)

    def confirm_password_reset(self, db: Session, *, email: str, code: str, new_password: str) -> UserAccount:
        reset_code = self._get_password_reset_code(db, email=email, code=code)
        now = self._now_provider()
        _ensure_code_usable(
            code=reset_code,
            now=now,
            invalid_error=PasswordResetCodeInvalidError,
            expired_error=PasswordResetCodeExpiredError,
            consumed_error=PasswordResetCodeConsumedError,
        )

        user = self._repository.get_user_by_id(db, reset_code.user_id)
        if user is None or user.normalized_email != normalize_email(email):
            raise PasswordResetCodeInvalidError("password reset code is invalid.")
        latest_code = self._repository.get_latest_password_reset_code(db, user_id=user.id)
        if latest_code is None or latest_code.id != reset_code.id:
            raise PasswordResetCodeInvalidError("password reset code is invalid.")

        password_hash = self._password_hasher.hash_password(new_password)
        self._repository.update_password_hash(
            db,
            user=user,
            password_hash=password_hash.password_hash,
            password_hash_algorithm=password_hash.algorithm,
            password_hash_version=password_hash.version,
            password_hash_params=password_hash.params,
            commit=False,
        )
        self._repository.consume_password_reset_code(db, code=reset_code, consumed_at=now, commit=False)
        self._repository.revoke_user_sessions(
            db,
            user_id=user.id,
            revoked_at=now,
            reason="password_reset",
            commit=False,
        )
        db.commit()
        db.refresh(user)
        return user

    def change_password(
        self,
        db: Session,
        *,
        user: UserAccount,
        current_password: str,
        new_password: str,
        current_session_id: str,
        sign_out_everywhere: bool = False,
    ) -> PasswordChangeResult:
        if not self._verify_password(user=user, password=current_password):
            raise PasswordChangeInvalidCurrentPasswordError("current password is invalid.")

        now = self._now_provider()
        password_hash = self._password_hasher.hash_password(new_password)
        self._repository.update_password_hash(
            db,
            user=user,
            password_hash=password_hash.password_hash,
            password_hash_algorithm=password_hash.algorithm,
            password_hash_version=password_hash.version,
            password_hash_params=password_hash.params,
            commit=False,
        )
        revoked_sessions = self._repository.revoke_user_sessions(
            db,
            user_id=user.id,
            revoked_at=now,
            reason="password_change",
            except_session_id=None if sign_out_everywhere else current_session_id,
            commit=False,
        )
        db.commit()
        db.refresh(user)
        self._send_password_change_notification(user.email, changed_at=now)
        return PasswordChangeResult(user=user, revoked_sessions=revoked_sessions)

    def delete_account(
        self,
        db: Session,
        *,
        user: UserAccount,
        password: str,
    ) -> DeleteAccountResult:
        if not self._verify_password(user=user, password=password):
            raise DeleteAccountInvalidPasswordError("password is invalid.")

        now = self._now_provider()
        audit = self._repository.delete_user_account_and_owned_data(
            db,
            user=user,
            requested_at=now,
            deleted_at=now,
            commit=False,
        )
        deletion_receipt_id = audit.id
        deleted_at = audit.deleted_at
        db.commit()
        return DeleteAccountResult(deletion_receipt_id=deletion_receipt_id, deleted_at=deleted_at)

    def _create_email_verification_code(
        self,
        db: Session,
        *,
        user: UserAccount,
        resend_count: int,
    ) -> tuple[str, EmailVerificationCode]:
        now = self._now_provider()
        code = _generate_numeric_code(self._code_length)
        verification_code = self._repository.create_email_verification_code(
            db,
            user_id=user.id,
            code_hash=self._hash_code(EMAIL_VERIFICATION_PURPOSE, user.email, code),
            sent_to_email=user.email,
            expires_at=now + self._verification_code_ttl,
            resend_count=resend_count,
            rate_limited_until=now + self._resend_cooldown,
            created_at=now,
            commit=False,
        )
        return code, verification_code

    def _create_password_reset_code(self, db: Session, *, user: UserAccount) -> tuple[str, PasswordResetCode]:
        now = self._now_provider()
        code = _generate_numeric_code(self._code_length)
        reset_code = self._repository.create_password_reset_code(
            db,
            user_id=user.id,
            code_hash=self._hash_code(PASSWORD_RESET_PURPOSE, user.email, code),
            sent_to_email=user.email,
            expires_at=now + self._password_reset_code_ttl,
            created_at=now,
            commit=False,
        )
        return code, reset_code

    def _get_email_verification_code(self, db: Session, *, email: str, code: str) -> EmailVerificationCode:
        verification_code = self._repository.get_email_verification_code_by_hash(
            db,
            self._hash_code(EMAIL_VERIFICATION_PURPOSE, email, code),
        )
        if verification_code is None:
            raise EmailVerificationCodeInvalidError("email verification code is invalid.")
        return verification_code

    def _get_password_reset_code(self, db: Session, *, email: str, code: str) -> PasswordResetCode:
        reset_code = self._repository.get_password_reset_code_by_hash(
            db,
            self._hash_code(PASSWORD_RESET_PURPOSE, email, code),
        )
        if reset_code is None:
            raise PasswordResetCodeInvalidError("password reset code is invalid.")
        return reset_code

    def _hash_code(self, purpose: str, email: str, code: str) -> str:
        payload = f"{purpose}:{normalize_email(email)}:{code}".encode()
        return hmac.new(self._code_hash_secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()

    def _verify_password(self, *, user: UserAccount, password: str) -> bool:
        verification = self._password_hasher.verify_password(
            password=password,
            password_hash=user.password_hash,
            algorithm=user.password_hash_algorithm,
            version=user.password_hash_version,
            params=user.password_hash_params,
        )
        return verification.is_valid

    def _send_email_verification_code(self, email: str, code: str) -> None:
        self._email_sender.send(
            AuthEmailMessage(
                to_email=email,
                subject="Verify your Vinyl Listen account",
                body=f"Your Vinyl Listen verification code is {code}.",
                purpose=EMAIL_VERIFICATION_PURPOSE,
                code=code,
            )
        )

    def _send_password_reset_code(self, email: str, code: str, expires_at: datetime) -> None:
        self._email_sender.send(
            AuthEmailMessage(
                to_email=email,
                subject="Reset your Vinyl Listen password",
                body=f"Your Vinyl Listen password reset code is {code}. It expires at {expires_at.isoformat()}.",
                purpose=PASSWORD_RESET_PURPOSE,
                code=code,
            )
        )

    def _send_password_change_notification(self, email: str, *, changed_at: datetime) -> None:
        try:
            self._email_sender.send(
                AuthEmailMessage(
                    to_email=email,
                    subject="Your Vinyl Listen password was changed",
                    body=(
                        "Your Vinyl Listen password was changed at "
                        f"{changed_at.isoformat()}. If this was not you, reset your password immediately."
                    ),
                    purpose=PASSWORD_CHANGE_NOTIFICATION_PURPOSE,
                )
            )
        except AuthEmailDeliveryError:
            logger.exception("Password change notification email failed to send to=%s", email)


def _resolve_code_hash_secret(code_hash_secret: str | None) -> str:
    secret = code_hash_secret or settings.auth_code_hash_secret or settings.auth_access_token_secret
    if secret is None or not secret.strip():
        raise AuthAccountConfigurationError("AUTH_CODE_HASH_SECRET or AUTH_ACCESS_TOKEN_SECRET is required.")
    return secret


def _generate_numeric_code(length: int) -> str:
    upper_bound = 10**length
    return f"{secrets.randbelow(upper_bound):0{length}d}"


def _ensure_code_usable(
    *,
    code: EmailVerificationCode | PasswordResetCode,
    now: datetime,
    invalid_error: type[AuthAccountError],
    expired_error: type[AuthAccountError],
    consumed_error: type[AuthAccountError],
) -> None:
    if code.consumed_at is not None:
        raise consumed_error("code has already been used.")
    if _ensure_utc(code.expires_at) <= now:
        raise expired_error("code has expired.")
    if not code.sent_to_email:
        raise invalid_error("code is invalid.")


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
