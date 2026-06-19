from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.auth import UserEntitlement
from app.repositories.auth_repository import AuthRepository

OCR_IDENTIFY_CAPABILITY = "ocr_identify"
DEFAULT_ALLOWED_ENTITLEMENT_STATUSES = frozenset({"ACTIVE", "TRIAL", "TRIALING"})


@dataclass(frozen=True)
class CapabilityRule:
    capability: str
    window: timedelta | None
    plan_limits: Mapping[str, int | None]
    default_limit: int | None


@dataclass(frozen=True)
class UsageGrant:
    capability: str
    plan: str
    used_before: int
    used_after: int
    limit: int | None
    window_seconds: int | None
    reset_at: datetime | None


class FeatureGateError(Exception):
    def __init__(
        self,
        *,
        code: str,
        message: str,
        capability: str,
        plan: str | None = None,
        limit: int | None = None,
        used: int | None = None,
        reset_at: datetime | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.capability = capability
        self.plan = plan
        self.limit = limit
        self.used = used
        self.reset_at = reset_at


class EntitlementService:
    """Capability-name based usage checks for future paid or limited features."""

    def __init__(
        self,
        *,
        repository: AuthRepository | None = None,
        now_provider: Callable[[], datetime] | None = None,
        rules: Mapping[str, CapabilityRule] | None = None,
    ) -> None:
        self._repository = repository or AuthRepository()
        self._now_provider = now_provider or (lambda: datetime.now(UTC))
        self._rules = dict(rules or _default_capability_rules())

    def consume_usage(
        self,
        db: Session,
        *,
        user_id: str,
        capability: str,
        units: int = 1,
        event_metadata: dict | None = None,
    ) -> UsageGrant:
        if units <= 0:
            raise ValueError("usage units must be positive.")

        self._repository.lock_usage_counter(db, user_id=user_id, capability=capability)
        try:
            grant = self.check_usage(db, user_id=user_id, capability=capability, units=units)
            self.record_usage(
                db,
                user_id=user_id,
                capability=capability,
                units=units,
                event_metadata=event_metadata,
            )
        except Exception:
            db.rollback()
            raise
        return grant

    def check_usage(
        self,
        db: Session,
        *,
        user_id: str,
        capability: str,
        units: int = 1,
    ) -> UsageGrant:
        if units <= 0:
            raise ValueError("usage units must be positive.")

        now = self._now()
        entitlement = self._repository.get_entitlement(db, user_id)
        if entitlement is None:
            entitlement = UserEntitlement(user_id=user_id, plan="FREE", status="ACTIVE")
        self._ensure_entitlement_active(entitlement, now=now, capability=capability)

        rule = self._rules.get(capability)
        since = now - rule.window if rule is not None and rule.window is not None else None
        used_before = self._repository.sum_usage_units(db, user_id=user_id, capability=capability, since=since)
        limit = _resolve_limit(rule, plan=entitlement.plan)
        reset_at = (since + rule.window) if since is not None and rule is not None and rule.window is not None else None

        if limit is not None and used_before + units > limit:
            raise FeatureGateError(
                code="feature_usage_limit_exceeded",
                message="Usage limit reached for this feature.",
                capability=capability,
                plan=entitlement.plan,
                limit=limit,
                used=used_before,
                reset_at=reset_at,
            )

        return UsageGrant(
            capability=capability,
            plan=entitlement.plan,
            used_before=used_before,
            used_after=used_before + units,
            limit=limit,
            window_seconds=int(rule.window.total_seconds()) if rule is not None and rule.window is not None else None,
            reset_at=reset_at,
        )

    def record_usage(
        self,
        db: Session,
        *,
        user_id: str,
        capability: str,
        units: int = 1,
        event_metadata: dict | None = None,
    ) -> None:
        if units <= 0:
            raise ValueError("usage units must be positive.")

        now = self._now()
        entitlement = self._repository.get_entitlement(db, user_id)
        if entitlement is None:
            entitlement = self._repository.ensure_entitlement(db, user_id=user_id, commit=False)
        self._ensure_entitlement_active(entitlement, now=now, capability=capability)
        self._repository.record_usage_event(
            db,
            user_id=user_id,
            capability=capability,
            occurred_at=now,
            units=units,
            event_metadata=event_metadata,
            commit=False,
        )
        db.commit()

    def _ensure_entitlement_active(self, entitlement: UserEntitlement, *, now: datetime, capability: str) -> None:
        status = entitlement.status.upper()
        if status not in DEFAULT_ALLOWED_ENTITLEMENT_STATUSES:
            raise FeatureGateError(
                code="feature_not_available",
                message="This feature is not available for the current account status.",
                capability=capability,
                plan=entitlement.plan,
            )
        if entitlement.valid_until is not None and _ensure_utc(entitlement.valid_until) <= now:
            raise FeatureGateError(
                code="feature_not_available",
                message="This feature entitlement has expired.",
                capability=capability,
                plan=entitlement.plan,
            )

    def _now(self) -> datetime:
        return _ensure_utc(self._now_provider())


def _default_capability_rules() -> dict[str, CapabilityRule]:
    window = timedelta(days=settings.entitlement_ocr_identify_window_days)
    return {
        OCR_IDENTIFY_CAPABILITY: CapabilityRule(
            capability=OCR_IDENTIFY_CAPABILITY,
            window=window,
            plan_limits={
                "FREE": settings.entitlement_ocr_identify_free_limit,
                "TRIAL": settings.entitlement_ocr_identify_trial_limit,
                "PLUS": None,
                "PRO": None,
            },
            default_limit=settings.entitlement_ocr_identify_free_limit,
        )
    }


def _resolve_limit(rule: CapabilityRule | None, *, plan: str) -> int | None:
    if rule is None:
        return None
    return rule.plan_limits.get(plan.upper(), rule.default_limit)


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
