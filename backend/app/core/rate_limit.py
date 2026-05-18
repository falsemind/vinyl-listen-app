import hashlib
import logging
import math
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from fastapi import Request

logger = logging.getLogger(__name__)

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


class RateLimiter(Protocol):
    def acquire(self, *, client_key: str, policy: RateLimitPolicy) -> RateLimitResult: ...

    def reset(self) -> None: ...


class RedisClientProtocol(Protocol):
    def eval(self, script: str, numkeys: int, *keys_and_args: object) -> object: ...

    def scan_iter(self, match: str) -> object: ...

    def delete(self, *names: object) -> object: ...


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


class RedisRateLimiter:
    _ACQUIRE_SCRIPT = """
local key = KEYS[1]
local redis_time = redis.call("TIME")
local now = tonumber(redis_time[1]) + (tonumber(redis_time[2]) / 1000000)
local limit = tonumber(ARGV[1])
local window_seconds = tonumber(ARGV[2])
local refill_rate = limit / window_seconds
local values = redis.call("HMGET", key, "tokens", "updated_at")
local tokens = tonumber(values[1])
local updated_at = tonumber(values[2])

if tokens == nil or updated_at == nil then
    tokens = limit
    updated_at = now
end

local elapsed_seconds = math.max(0, now - updated_at)
tokens = math.min(limit, tokens + (elapsed_seconds * refill_rate))

local allowed = 0
local retry_after_ms = 0
if tokens >= 1 then
    tokens = tokens - 1
    allowed = 1
else
    retry_after_ms = math.ceil(((1 - tokens) / refill_rate) * 1000)
end

redis.call("HSET", key, "tokens", tokens, "updated_at", now)
redis.call("EXPIRE", key, math.ceil(window_seconds * 2))

return {allowed, retry_after_ms, math.floor(tokens)}
"""

    def __init__(
        self,
        *,
        redis_client: RedisClientProtocol,
        key_prefix: str,
        fail_open: bool = True,
    ) -> None:
        self._redis_client = redis_client
        self._key_prefix = key_prefix.rstrip(":")
        self._fail_open = fail_open

    def acquire(self, *, client_key: str, policy: RateLimitPolicy) -> RateLimitResult:
        try:
            result = self._redis_client.eval(
                self._ACQUIRE_SCRIPT,
                1,
                self._redis_key(client_key=client_key, policy=policy),
                policy.limit,
                policy.window_seconds,
            )
            return self._parse_result(result)
        except Exception:
            if not self._fail_open:
                raise
            logger.warning(
                "Redis rate limiter unavailable; allowing request policy=%s",
                policy.name,
                exc_info=True,
            )
            return RateLimitResult(allowed=True, retry_after_seconds=0.0, remaining=policy.limit)

    def reset(self) -> None:
        try:
            keys = list(self._redis_client.scan_iter(match=f"{self._key_prefix}:*"))
            if keys:
                self._redis_client.delete(*keys)
        except Exception:
            if not self._fail_open:
                raise
            logger.warning("Redis rate limiter reset failed", exc_info=True)

    def _redis_key(self, *, client_key: str, policy: RateLimitPolicy) -> str:
        key_hash = hashlib.sha256(f"{policy.name}:{client_key}".encode()).hexdigest()
        return f"{self._key_prefix}:{policy.name}:{key_hash}"

    @staticmethod
    def _parse_result(result: object) -> RateLimitResult:
        if not isinstance(result, list | tuple) or len(result) != 3:
            raise ValueError("Redis rate limiter returned an invalid response.")

        allowed_raw, retry_after_ms_raw, remaining_raw = result
        return RateLimitResult(
            allowed=bool(int(allowed_raw)),
            retry_after_seconds=max(0.0, int(retry_after_ms_raw) / 1000.0),
            remaining=max(0, int(remaining_raw)),
        )


def build_rate_limiter(
    *,
    backend: str,
    redis_url: str | None,
    redis_key_prefix: str,
    redis_fail_open: bool,
    redis_timeout_seconds: float,
) -> RateLimiter:
    if backend == "memory":
        return InMemoryRateLimiter()

    if backend != "redis":
        raise ValueError(f"Unsupported rate limiter backend: {backend}")
    if not redis_url:
        raise ValueError("Redis rate limiter backend requires inbound_rate_limit_redis_url.")
    if redis_timeout_seconds <= 0:
        raise ValueError("Redis rate limiter timeout must be positive.")

    try:
        from redis import Redis
    except ImportError as exc:
        raise RuntimeError("Redis rate limiter backend requires the redis package.") from exc

    return RedisRateLimiter(
        redis_client=Redis.from_url(
            redis_url,
            socket_connect_timeout=redis_timeout_seconds,
            socket_timeout=redis_timeout_seconds,
        ),
        key_prefix=redis_key_prefix,
        fail_open=redis_fail_open,
    )


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
