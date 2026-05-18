import os
import uuid

import pytest
from starlette.requests import Request

from app.core.rate_limit import (
    DEFAULT_RATE_LIMIT_POLICY_NAME,
    IDENTIFY_RATE_LIMIT_POLICY_NAME,
    ClientKeyResolver,
    InMemoryRateLimiter,
    RateLimitPolicy,
    RedisRateLimiter,
    build_rate_limit_policies,
    resolve_rate_limit_policy,
)


class FakeClock:
    def __init__(self) -> None:
        self._now = 0.0

    def __call__(self) -> float:
        return self._now

    def advance(self, seconds: float) -> None:
        self._now += seconds


class FakeRedisClient:
    def __init__(self, *, reply: list[int] | None = None, error: Exception | None = None) -> None:
        self.reply = reply or [1, 0, 0]
        self.error = error
        self.eval_calls: list[tuple[object, ...]] = []
        self.deleted_names: tuple[object, ...] = ()

    def eval(self, script: str, numkeys: int, *keys_and_args: object) -> object:
        self.eval_calls.append((script, numkeys, *keys_and_args))
        if self.error is not None:
            raise self.error
        return self.reply

    def scan_iter(self, match: str) -> list[str]:
        return [match.replace("*", "key")]

    def delete(self, *names: object) -> object:
        self.deleted_names = names
        return len(names)


def test_rate_limiter_rejects_until_bucket_refills() -> None:
    clock = FakeClock()
    limiter = InMemoryRateLimiter(clock=clock)
    policy = RateLimitPolicy(name="test", limit=2, window_seconds=60.0)

    assert limiter.acquire(client_key="client-a", policy=policy).allowed is True
    assert limiter.acquire(client_key="client-a", policy=policy).allowed is True

    rejected = limiter.acquire(client_key="client-a", policy=policy)
    assert rejected.allowed is False
    assert rejected.retry_after_seconds == pytest.approx(30.0)

    clock.advance(30.0)
    accepted = limiter.acquire(client_key="client-a", policy=policy)
    assert accepted.allowed is True
    assert accepted.remaining == 0


def test_rate_limiter_keeps_client_keys_independent() -> None:
    limiter = InMemoryRateLimiter(clock=FakeClock())
    policy = RateLimitPolicy(name="test", limit=1, window_seconds=60.0)

    assert limiter.acquire(client_key="client-a", policy=policy).allowed is True
    assert limiter.acquire(client_key="client-a", policy=policy).allowed is False
    assert limiter.acquire(client_key="client-b", policy=policy).allowed is True


def test_rate_limiter_prunes_idle_buckets() -> None:
    clock = FakeClock()
    limiter = InMemoryRateLimiter(clock=clock)
    policy = RateLimitPolicy(name="test", limit=1, window_seconds=60.0)

    for index in range(10):
        assert limiter.acquire(client_key=f"client-{index}", policy=policy).allowed is True

    assert limiter.bucket_count() == 10

    clock.advance(60.0)
    assert limiter.acquire(client_key="active-client", policy=policy).allowed is True

    assert limiter.bucket_count() == 1


def test_redis_rate_limiter_allows_from_eval_response() -> None:
    redis_client = FakeRedisClient(reply=[1, 0, 4])
    limiter = RedisRateLimiter(
        redis_client=redis_client,
        key_prefix="test-prefix",
    )
    policy = RateLimitPolicy(name="test", limit=5, window_seconds=60.0)

    result = limiter.acquire(client_key="client-a", policy=policy)

    assert result.allowed is True
    assert result.retry_after_seconds == 0.0
    assert result.remaining == 4
    assert redis_client.eval_calls[0][1] == 1
    assert str(redis_client.eval_calls[0][2]).startswith("test-prefix:test:")


def test_redis_rate_limiter_rejects_from_eval_response() -> None:
    limiter = RedisRateLimiter(
        redis_client=FakeRedisClient(reply=[0, 1250, 0]),
        key_prefix="test-prefix",
    )
    policy = RateLimitPolicy(name="test", limit=1, window_seconds=60.0)

    result = limiter.acquire(client_key="client-a", policy=policy)

    assert result.allowed is False
    assert result.retry_after_seconds == pytest.approx(1.25)
    assert result.remaining == 0


def test_redis_rate_limiter_fails_open_when_redis_is_unavailable() -> None:
    limiter = RedisRateLimiter(
        redis_client=FakeRedisClient(error=TimeoutError("redis unavailable")),
        key_prefix="test-prefix",
        fail_open=True,
    )
    policy = RateLimitPolicy(name="test", limit=10, window_seconds=60.0)

    result = limiter.acquire(client_key="client-a", policy=policy)

    assert result.allowed is True
    assert result.retry_after_seconds == 0.0
    assert result.remaining == 10


def test_redis_rate_limiter_can_fail_closed_when_configured() -> None:
    limiter = RedisRateLimiter(
        redis_client=FakeRedisClient(error=TimeoutError("redis unavailable")),
        key_prefix="test-prefix",
        fail_open=False,
    )
    policy = RateLimitPolicy(name="test", limit=10, window_seconds=60.0)

    with pytest.raises(TimeoutError):
        limiter.acquire(client_key="client-a", policy=policy)


@pytest.mark.skipif(
    not os.environ.get("TEST_REDIS_URL"),
    reason="Set TEST_REDIS_URL to run Redis rate limiter integration tests.",
)
def test_redis_rate_limiter_enforces_shared_bucket_with_real_redis() -> None:
    from redis import Redis

    redis_url = os.environ["TEST_REDIS_URL"]
    redis_client = Redis.from_url(redis_url)
    try:
        redis_client.ping()
    except Exception as exc:
        pytest.skip(f"Redis unavailable: {exc}")

    prefix = f"test-rate-limit:{uuid.uuid4()}"
    first_limiter = RedisRateLimiter(redis_client=redis_client, key_prefix=prefix)
    second_limiter = RedisRateLimiter(redis_client=redis_client, key_prefix=prefix)
    policy = RateLimitPolicy(name="test", limit=1, window_seconds=60.0)

    try:
        assert first_limiter.acquire(client_key="client-a", policy=policy).allowed is True
        rejected = second_limiter.acquire(client_key="client-a", policy=policy)
        assert rejected.allowed is False
        assert rejected.retry_after_seconds == pytest.approx(60.0)
    finally:
        first_limiter.reset()


def test_client_key_resolver_ignores_proxy_headers_by_default() -> None:
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/v1/releases",
            "headers": [(b"x-forwarded-for", b"203.0.113.1")],
            "client": ("10.0.0.1", 1234),
        }
    )

    assert ClientKeyResolver().resolve(request) == "10.0.0.1"


def test_client_key_resolver_prefers_forwarded_for_when_proxy_headers_are_trusted() -> None:
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/v1/releases",
            "headers": [(b"x-forwarded-for", b"203.0.113.1, 10.0.0.2")],
            "client": ("10.0.0.1", 1234),
        }
    )

    assert ClientKeyResolver(trust_proxy_headers=True).resolve(request) == "203.0.113.1"


def test_route_policy_table_matches_phase_one_contract() -> None:
    policies = build_rate_limit_policies(default_limit=10, identify_limit=2, window_seconds=60.0)

    route_expectations = [
        ("GET", "/", None),
        ("GET", "/favicon.ico", None),
        ("GET", "/api/v1/health", None),
        ("GET", "/api/v1/health/runtime", None),
        ("GET", "/api/v1/releases/search", DEFAULT_RATE_LIMIT_POLICY_NAME),
        ("GET", "/api/v1/identify/jobs/job-123", DEFAULT_RATE_LIMIT_POLICY_NAME),
        ("POST", "/api/v1/identify", IDENTIFY_RATE_LIMIT_POLICY_NAME),
        ("POST", "/api/v1/identify/jobs", IDENTIFY_RATE_LIMIT_POLICY_NAME),
    ]

    for method, path, expected_policy_name in route_expectations:
        policy = resolve_rate_limit_policy(method=method, path=path, policies=policies)
        assert (policy.name if policy else None) == expected_policy_name
