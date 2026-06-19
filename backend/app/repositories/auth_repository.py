import hashlib
import struct
from datetime import datetime
from uuid import uuid4

from sqlalchemy import delete, func, inspect, select, text
from sqlalchemy.orm import Session

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
from app.models.sessions import SessionGroups, Sessions, SessionTracks
from app.models.sessions_moods import SessionsMoods
from app.models.spotify_listening import (
    SpotifyAlbumStats,
    SpotifyArtistStats,
    SpotifyHourlyStats,
    SpotifyListeningEvent,
    SpotifyListeningImportBatch,
    SpotifyMonthlyArtistStats,
    SpotifySkipStats,
    SpotifyTrackStats,
    SpotifyVinylArtistMatch,
    SpotifyVinylReleaseMatch,
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

    def record_auth_audit_event(
        self,
        db: Session,
        *,
        event_type: str,
        outcome: str,
        occurred_at: datetime,
        user_id: str | None = None,
        session_id: str | None = None,
        event_details: dict | None = None,
        event_id: str | None = None,
        commit: bool = True,
    ) -> AuthAuditEvent:
        event = AuthAuditEvent(
            id=event_id or _new_id(),
            user_id=user_id,
            session_id=session_id,
            event_type=event_type,
            outcome=outcome,
            occurred_at=occurred_at,
            event_details=event_details,
        )
        return _persist(db, event, commit=commit)

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
        except_session_id: str | None = None,
        commit: bool = True,
    ) -> int:
        query = db.query(AuthSession).filter(AuthSession.user_id == user_id).filter(AuthSession.revoked_at.is_(None))
        if except_session_id is not None:
            query = query.filter(AuthSession.id != except_session_id)
        sessions = query.all()
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
        created_at: datetime | None = None,
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
        if created_at is not None:
            code.created_at = created_at
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
            .order_by(EmailVerificationCode.created_at.desc(), EmailVerificationCode.id.desc())
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

    def record_email_verification_failed_attempt(
        self,
        db: Session,
        *,
        code: EmailVerificationCode,
        attempt_limit: int,
        lock_until: datetime | None = None,
        commit: bool = True,
    ) -> EmailVerificationCode:
        code.failed_attempt_count += 1
        if code.failed_attempt_count >= attempt_limit:
            code.failed_attempt_limited_until = lock_until
        return _persist(db, code, commit=commit)

    def create_password_reset_code(
        self,
        db: Session,
        *,
        user_id: str,
        code_hash: str,
        sent_to_email: str,
        expires_at: datetime,
        created_at: datetime | None = None,
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
        if created_at is not None:
            code.created_at = created_at
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
            .order_by(PasswordResetCode.created_at.desc(), PasswordResetCode.id.desc())
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

    def record_password_reset_failed_attempt(
        self,
        db: Session,
        *,
        code: PasswordResetCode,
        attempt_limit: int,
        lock_until: datetime | None = None,
        commit: bool = True,
    ) -> PasswordResetCode:
        code.failed_attempt_count += 1
        if code.failed_attempt_count >= attempt_limit:
            code.failed_attempt_limited_until = lock_until
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

    def lock_usage_counter(self, db: Session, *, user_id: str, capability: str) -> None:
        if db.get_bind().dialect.name != "postgresql":
            return

        key_1, key_2 = _usage_advisory_lock_keys(user_id=user_id, capability=capability)
        db.execute(
            text("SELECT pg_advisory_xact_lock(:key_1, :key_2)"),
            {"key_1": key_1, "key_2": key_2},
        )

    def sum_usage_units(
        self,
        db: Session,
        *,
        user_id: str,
        capability: str,
        since: datetime | None = None,
    ) -> int:
        query = db.query(func.coalesce(func.sum(UsageEvent.units), 0)).filter(
            UsageEvent.user_id == user_id,
            UsageEvent.capability == capability,
        )
        if since is not None:
            query = query.filter(UsageEvent.occurred_at >= since)
        return int(query.scalar() or 0)

    def create_account_deletion_audit(
        self,
        db: Session,
        *,
        requested_at: datetime,
        deleted_at: datetime,
        audit_id: str | None = None,
        commit: bool = True,
    ) -> AccountDeletionAudit:
        audit = AccountDeletionAudit(
            id=audit_id or _new_id(),
            event_type="account_deleted",
            requested_at=requested_at,
            deleted_at=deleted_at,
        )
        return _persist(db, audit, commit=commit)

    def delete_user_account_and_owned_data(
        self,
        db: Session,
        *,
        user: UserAccount,
        requested_at: datetime,
        deleted_at: datetime,
        audit_id: str | None = None,
        commit: bool = True,
    ) -> AccountDeletionAudit:
        self._delete_user_owned_data(db, user_id=user.id)
        audit = self.create_account_deletion_audit(
            db,
            requested_at=requested_at,
            deleted_at=deleted_at,
            audit_id=audit_id,
            commit=False,
        )
        db.delete(user)
        if commit:
            db.commit()
        else:
            db.flush()
        return audit

    def _delete_user_owned_data(self, db: Session, *, user_id: str) -> None:
        existing_tables = _existing_table_names(db)

        if _table_exists(existing_tables, AiChatMessageRecord) and _table_exists(existing_tables, AiChatSession):
            db.execute(
                delete(AiChatMessageRecord).where(
                    AiChatMessageRecord.conversation_id.in_(
                        select(AiChatSession.id).where(AiChatSession.user_id == user_id)
                    )
                )
            )
        if _table_exists(existing_tables, SessionTracks) and _table_exists(existing_tables, Sessions):
            db.execute(
                delete(SessionTracks).where(
                    SessionTracks.session_id.in_(select(Sessions.id).where(Sessions.user_id == user_id))
                )
            )

        for model in (
            AuthAuditEvent,
            ConsumedRefreshToken,
            EmailVerificationCode,
            PasswordResetCode,
            UsageEvent,
            UserEntitlement,
            ProviderIntegration,
            CollectionSettings,
            ReleaseCollectionFolder,
            ReleaseCollectionMembership,
            CollectionFolder,
            CollectionSyncJob,
            IdentifyJob,
            SessionsMoods,
            SpotifyVinylReleaseMatch,
            SpotifyVinylArtistMatch,
            SpotifySkipStats,
            SpotifyMonthlyArtistStats,
            SpotifyHourlyStats,
            SpotifyTrackStats,
            SpotifyAlbumStats,
            SpotifyArtistStats,
            SpotifyListeningEvent,
            SpotifyListeningImportBatch,
            AiChatSession,
            Sessions,
            SessionGroups,
            AuthSession,
        ):
            _delete_model_by_user_id(db, model, user_id=user_id, existing_tables=existing_tables)

        db.flush()


def _new_id() -> str:
    return str(uuid4())


def _usage_advisory_lock_keys(*, user_id: str, capability: str) -> tuple[int, int]:
    digest = hashlib.blake2b(f"usage:{user_id}:{capability}".encode(), digest_size=8).digest()
    return struct.unpack("!ii", digest)


def _existing_table_names(db: Session) -> set[str]:
    return set(inspect(db.connection()).get_table_names())


def _table_exists(existing_tables: set[str], model: type) -> bool:
    return model.__table__.name in existing_tables


def _delete_model_by_user_id(
    db: Session,
    model: type,
    *,
    user_id: str,
    existing_tables: set[str],
) -> None:
    if not _table_exists(existing_tables, model):
        return
    db.execute(delete(model).where(model.user_id == user_id))


def _persist[T](db: Session, model: T, *, commit: bool) -> T:
    db.add(model)
    if commit:
        db.commit()
        db.refresh(model)
    else:
        db.flush()
    return model
