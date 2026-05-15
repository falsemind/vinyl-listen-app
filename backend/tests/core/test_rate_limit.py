import pytest
from starlette.requests import Request

from app.core.rate_limit import (
    DEFAULT_RATE_LIMIT_POLICY_NAME,
    IDENTIFY_RATE_LIMIT_POLICY_NAME,
    ClientKeyResolver,
    InMemoryRateLimiter,
    RateLimitPolicy,
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
