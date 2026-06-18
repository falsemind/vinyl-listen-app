from datetime import datetime
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models.auth import (
    AuthSession,
    ConsumedRefreshToken,
    EmailVerificationCode,
    PasswordResetCode,
    UsageEvent,
    UserAccount,
    UserEntitlement,
)


def normalize_email(email: str) -> str:
    """Normalize an email address for account uniqueness checks."""
    return email.strip().casefold()


class AuthRepository:
    """Repository for account, session, code, entitlement, and usage records."""

    def create_user_account(
        self,
        db: Session,
        *,
        email: str,
        password_hash: str,
        password_hash_algorithm: str,
        password_hash_version: int = 1,
        password_hash_params: dict | None = None,
        user_id: str | None = None,
        commit: bool = True,
    ) -> UserAccount:
        account = UserAccount(
            id=user_id or _new_id(),
            email=email.strip(),
            normalized_email=normalize_email(email),
            password_hash=password_hash,
            password_hash_algorithm=password_hash_algorithm,
            password_hash_version=password_hash_version,
            password_hash_params=password_hash_params,
        )
        return _persist(db, account, commit=commit)

    def get_user_by_id(self, db: Session, user_id: str) -> UserAccount | None:
        return db.query(UserAccount).filter(UserAccount.id == user_id).one_or_none()

    def get_user_by_normalized_email(self, db: Session, email: str) -> UserAccount | None:
        return db.query(UserAccount).filter(UserAccount.normalized_email == normalize_email(email)).one_or_none()

    def mark_email_verified(
        self,
        db: Session,
        *,
        user: UserAccount,
        verified_at: datetime,
        commit: bool = True,
    ) -> UserAccount:
        user.email_verified_at = verified_at
        return _persist(db, user, commit=commit)

    def update_password_hash(
        self,
        db: Session,
        *,
        user: UserAccount,
        password_hash: str,
        password_hash_algorithm: str,
        password_hash_version: int,
        password_hash_params: dict | None,
        commit: bool = True,
    ) -> UserAccount:
        user.password_hash = password_hash
        user.password_hash_algorithm = password_hash_algorithm
        user.password_hash_version = password_hash_version
        user.password_hash_params = password_hash_params
        return _persist(db, user, commit=commit)

    def create_auth_session(
        self,
        db: Session,
        *,
        user_id: str,
        refresh_token_hash: str,
        last_activity_at: datetime,
        expires_at: datetime,
        device_label: str | None = None,
        session_id: str | None = None,
        commit: bool = True,
    ) -> AuthSession:
        auth_session = AuthSession(
            id=session_id or _new_id(),
            user_id=user_id,
            refresh_token_hash=refresh_token_hash,
            device_label=device_label,
            last_activity_at=last_activity_at,
            expires_at=expires_at,
        )
        return _persist(db, auth_session, commit=commit)

    def get_auth_session_by_refresh_token_hash(
        self,
        db: Session,
        refresh_token_hash: str,
    ) -> AuthSession | None:
        return db.query(AuthSession).filter(AuthSession.refresh_token_hash == refresh_token_hash).one_or_none()

    def get_auth_session_by_id(self, db: Session, session_id: str) -> AuthSession | None:
        return db.query(AuthSession).filter(AuthSession.id == session_id).one_or_none()

    def touch_auth_session(
        self,
        db: Session,
        *,
        auth_session: AuthSession,
        last_activity_at: datetime,
        refresh_token_hash: str | None = None,
        expires_at: datetime | None = None,
        commit: bool = True,
    ) -> AuthSession:
        auth_session.last_activity_at = last_activity_at
        if refresh_token_hash is not None:
            auth_session.refresh_token_hash = refresh_token_hash
        if expires_at is not None:
            auth_session.expires_at = expires_at
        return _persist(db, auth_session, commit=commit)

    def revoke_auth_session(
        self,
        db: Session,
        *,
        auth_session: AuthSession,
        revoked_at: datetime,
        reason: str,
        commit: bool = True,
    ) -> AuthSession:
        auth_session.revoked_at = revoked_at
        auth_session.revoke_reason = reason
        return _persist(db, auth_session, commit=commit)

    def revoke_user_sessions(
        self,
        db: Session,
        *,
        user_id: str,
        revoked_at: datetime,
        reason: str,
        commit: bool = True,
    ) -> int:
        sessions = (
            db.query(AuthSession).filter(AuthSession.user_id == user_id).filter(AuthSession.revoked_at.is_(None)).all()
        )
        for auth_session in sessions:
            auth_session.revoked_at = revoked_at
            auth_session.revoke_reason = reason
            db.add(auth_session)

        if commit:
            db.commit()
        else:
            db.flush()
        return len(sessions)

    def create_consumed_refresh_token(
        self,
        db: Session,
        *,
        session_id: str,
        user_id: str,
        refresh_token_hash: str,
        consumed_at: datetime,
        expires_at: datetime,
        consumed_token_id: str | None = None,
        commit: bool = True,
    ) -> ConsumedRefreshToken:
        consumed_token = ConsumedRefreshToken(
            id=consumed_token_id or _new_id(),
            session_id=session_id,
            user_id=user_id,
            refresh_token_hash=refresh_token_hash,
            consumed_at=consumed_at,
            expires_at=expires_at,
        )
        return _persist(db, consumed_token, commit=commit)

    def get_consumed_refresh_token_by_hash(
        self,
        db: Session,
        refresh_token_hash: str,
    ) -> ConsumedRefreshToken | None:
        return (
            db.query(ConsumedRefreshToken)
            .filter(ConsumedRefreshToken.refresh_token_hash == refresh_token_hash)
            .one_or_none()
        )

    def create_email_verification_code(
        self,
        db: Session,
        *,
        user_id: str,
        code_hash: str,
        sent_to_email: str,
        expires_at: datetime,
        resend_count: int = 0,
        rate_limited_until: datetime | None = None,
        code_id: str | None = None,
        commit: bool = True,
    ) -> EmailVerificationCode:
        code = EmailVerificationCode(
            id=code_id or _new_id(),
            user_id=user_id,
            code_hash=code_hash,
            sent_to_email=sent_to_email,
            expires_at=expires_at,
            resend_count=resend_count,
            rate_limited_until=rate_limited_until,
        )
        return _persist(db, code, commit=commit)

    def get_latest_email_verification_code(
        self,
        db: Session,
        *,
        user_id: str,
    ) -> EmailVerificationCode | None:
        return (
            db.query(EmailVerificationCode)
            .filter(EmailVerificationCode.user_id == user_id)
            .order_by(EmailVerificationCode.expires_at.desc(), EmailVerificationCode.id.desc())
            .first()
        )

    def get_email_verification_code_by_hash(
        self,
        db: Session,
        code_hash: str,
    ) -> EmailVerificationCode | None:
        return db.query(EmailVerificationCode).filter(EmailVerificationCode.code_hash == code_hash).one_or_none()

    def consume_email_verification_code(
        self,
        db: Session,
        *,
        code: EmailVerificationCode,
        consumed_at: datetime,
        commit: bool = True,
    ) -> EmailVerificationCode:
        code.consumed_at = consumed_at
        return _persist(db, code, commit=commit)

    def create_password_reset_code(
        self,
        db: Session,
        *,
        user_id: str,
        code_hash: str,
        sent_to_email: str,
        expires_at: datetime,
        code_id: str | None = None,
        commit: bool = True,
    ) -> PasswordResetCode:
        code = PasswordResetCode(
            id=code_id or _new_id(),
            user_id=user_id,
            code_hash=code_hash,
            sent_to_email=sent_to_email,
            expires_at=expires_at,
        )
        return _persist(db, code, commit=commit)

    def get_password_reset_code_by_hash(
        self,
        db: Session,
        code_hash: str,
    ) -> PasswordResetCode | None:
        return db.query(PasswordResetCode).filter(PasswordResetCode.code_hash == code_hash).one_or_none()

    def get_latest_password_reset_code(
        self,
        db: Session,
        *,
        user_id: str,
    ) -> PasswordResetCode | None:
        return (
            db.query(PasswordResetCode)
            .filter(PasswordResetCode.user_id == user_id)
            .order_by(PasswordResetCode.expires_at.desc(), PasswordResetCode.id.desc())
            .first()
        )

    def consume_password_reset_code(
        self,
        db: Session,
        *,
        code: PasswordResetCode,
        consumed_at: datetime,
        commit: bool = True,
    ) -> PasswordResetCode:
        code.consumed_at = consumed_at
        return _persist(db, code, commit=commit)

    def consume_unconsumed_password_reset_codes(
        self,
        db: Session,
        *,
        user_id: str,
        consumed_at: datetime,
        commit: bool = True,
    ) -> int:
        codes = (
            db.query(PasswordResetCode)
            .filter(PasswordResetCode.user_id == user_id)
            .filter(PasswordResetCode.consumed_at.is_(None))
            .all()
        )
        for code in codes:
            code.consumed_at = consumed_at
            db.add(code)

        if commit:
            db.commit()
        else:
            db.flush()
        return len(codes)

    def get_entitlement(self, db: Session, user_id: str) -> UserEntitlement | None:
        return db.query(UserEntitlement).filter(UserEntitlement.user_id == user_id).one_or_none()

    def ensure_entitlement(
        self,
        db: Session,
        *,
        user_id: str,
        plan: str = "FREE",
        status: str = "ACTIVE",
        commit: bool = True,
    ) -> UserEntitlement:
        entitlement = self.get_entitlement(db, user_id)
        if entitlement is None:
            entitlement = UserEntitlement(user_id=user_id, plan=plan, status=status)
        else:
            entitlement.plan = plan
            entitlement.status = status
        return _persist(db, entitlement, commit=commit)

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
        event = UsageEvent(
            id=event_id or _new_id(),
            user_id=user_id,
            capability=capability,
            units=units,
            occurred_at=occurred_at,
            event_metadata=event_metadata,
        )
        return _persist(db, event, commit=commit)


def _new_id() -> str:
    return str(uuid4())


def _persist[T](db: Session, model: T, *, commit: bool) -> T:
    db.add(model)
    if commit:
        db.commit()
        db.refresh(model)
    else:
        db.flush()
    return model
