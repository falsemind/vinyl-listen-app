import math
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

from fastapi import Request

RATE_LIMIT_ERROR_CODE = "rate_limited"
RATE_LIMIT_ERROR_MESSAGE = "Too many requests. Please retry later."

DEFAULT_RATE_LIMIT_POLICY_NAME = "default"
IDENTIFY_RATE_LIMIT_POLICY_NAME = "identify"

EXEMPT_PATHS = {"/", "/favicon.ico"}
EXEMPT_PATH_PREFIXES = ("/api/v1/health",)
IDENTIFY_LIMITED_ROUTES = {
    ("POST", "/api/v1/identify"),
    ("POST", "/api/v1/identify/jobs"),
}


@dataclass(frozen=True, slots=True)
class RateLimitPolicy:
    name: str
    limit: int
    window_seconds: float

    def __post_init__(self) -> None:
        if self.limit <= 0:
            raise ValueError("Rate limit must be positive.")
        if self.window_seconds <= 0:
            raise ValueError("Rate limit window must be positive.")


@dataclass(frozen=True, slots=True)
class RateLimitResult:
    allowed: bool
    retry_after_seconds: float
    remaining: int


@dataclass(slots=True)
class _Bucket:
    tokens: float
    updated_at: float
    window_seconds: float


class ClientKeyResolver:
    def __init__(self, *, trust_proxy_headers: bool = False) -> None:
        self._trust_proxy_headers = trust_proxy_headers

    def resolve(self, request: Request) -> str:
        if self._trust_proxy_headers:
            forwarded_for = request.headers.get("x-forwarded-for")
            if forwarded_for:
                client_ip = forwarded_for.split(",", maxsplit=1)[0].strip()
                if client_ip:
                    return client_ip

            real_ip = request.headers.get("x-real-ip")
            if real_ip:
                return real_ip.strip()

        if request.client is not None and request.client.host:
            return request.client.host

        return "unknown"


class InMemoryRateLimiter:
    def __init__(self, *, clock: Callable[[], float] | None = None) -> None:
        self._clock = clock or time.monotonic
        self._buckets: dict[tuple[str, str], _Bucket] = {}
        self._lock = threading.Lock()

    def acquire(self, *, client_key: str, policy: RateLimitPolicy) -> RateLimitResult:
        now = self._clock()
        bucket_key = (client_key, policy.name)
        refill_rate = policy.limit / policy.window_seconds

        with self._lock:
            self._prune_expired_buckets(now)
            bucket = self._buckets.get(bucket_key)
            if bucket is None:
                bucket = _Bucket(
                    tokens=float(policy.limit),
                    updated_at=now,
                    window_seconds=policy.window_seconds,
                )

            elapsed_seconds = max(0.0, now - bucket.updated_at)
            tokens = min(float(policy.limit), bucket.tokens + (elapsed_seconds * refill_rate))

            if tokens >= 1.0:
                tokens -= 1.0
                self._buckets[bucket_key] = _Bucket(
                    tokens=tokens,
                    updated_at=now,
                    window_seconds=policy.window_seconds,
                )
                return RateLimitResult(
                    allowed=True,
                    retry_after_seconds=0.0,
                    remaining=math.floor(tokens),
                )

            retry_after_seconds = max(0.0, (1.0 - tokens) / refill_rate)
            self._buckets[bucket_key] = _Bucket(
                tokens=tokens,
                updated_at=now,
                window_seconds=policy.window_seconds,
            )
            return RateLimitResult(
                allowed=False,
                retry_after_seconds=retry_after_seconds,
                remaining=0,
            )

    def reset(self) -> None:
        with self._lock:
            self._buckets.clear()

    def bucket_count(self) -> int:
        with self._lock:
            return len(self._buckets)

    def _prune_expired_buckets(self, now: float) -> None:
        expired_keys = [
            bucket_key
            for bucket_key, bucket in self._buckets.items()
            if now - bucket.updated_at >= bucket.window_seconds
        ]
        for bucket_key in expired_keys:
            del self._buckets[bucket_key]


def build_rate_limit_policies(
    *,
    default_limit: int,
    identify_limit: int,
    window_seconds: float,
) -> dict[str, RateLimitPolicy]:
    return {
        DEFAULT_RATE_LIMIT_POLICY_NAME: RateLimitPolicy(
            name=DEFAULT_RATE_LIMIT_POLICY_NAME,
            limit=default_limit,
            window_seconds=window_seconds,
        ),
        IDENTIFY_RATE_LIMIT_POLICY_NAME: RateLimitPolicy(
            name=IDENTIFY_RATE_LIMIT_POLICY_NAME,
            limit=identify_limit,
            window_seconds=window_seconds,
        ),
    }


def resolve_rate_limit_policy(
    *,
    method: str,
    path: str,
    policies: dict[str, RateLimitPolicy],
) -> RateLimitPolicy | None:
    normalized_method = method.upper()

    if path in EXEMPT_PATHS:
        return None
    if any(path.startswith(prefix) for prefix in EXEMPT_PATH_PREFIXES):
        return None
    if (normalized_method, path) in IDENTIFY_LIMITED_ROUTES:
        return policies[IDENTIFY_RATE_LIMIT_POLICY_NAME]
    if path.startswith("/api/v1/"):
        return policies[DEFAULT_RATE_LIMIT_POLICY_NAME]

    return None
