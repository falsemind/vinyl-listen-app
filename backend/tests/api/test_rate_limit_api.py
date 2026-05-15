from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.core.rate_limit import InMemoryRateLimiter, build_rate_limit_policies
from app.main import app


@pytest.fixture
def rate_limited_app() -> Iterator[None]:
    original_policies = app.state.rate_limit_policies
    original_limiter = app.state.rate_limiter

    app.state.rate_limit_policies = build_rate_limit_policies(
        default_limit=1,
        identify_limit=1,
        window_seconds=60.0,
    )
    app.state.rate_limiter = InMemoryRateLimiter()

    try:
        yield
    finally:
        app.state.rate_limit_policies = original_policies
        app.state.rate_limiter = original_limiter
        app.state.rate_limiter.reset()


@pytest.mark.usefixtures("rate_limited_app")
def test_default_api_limit_returns_structured_429() -> None:
    headers = {"x-forwarded-for": "198.51.100.10"}

    with TestClient(app) as client:
        first_response = client.get("/api/v1/not-found", headers=headers)
        second_response = client.get("/api/v1/not-found", headers=headers)

    assert first_response.status_code == 404
    assert second_response.status_code == 429
    assert second_response.headers["Retry-After"] == "60"
    assert second_response.json() == {
        "error": {
            "code": "rate_limited",
            "message": "Too many requests. Please retry later.",
        }
    }


@pytest.mark.usefixtures("rate_limited_app")
def test_identify_create_uses_identify_policy() -> None:
    headers = {"x-forwarded-for": "198.51.100.20"}

    with TestClient(app) as client:
        first_response = client.post("/api/v1/identify/jobs", headers=headers)
        second_response = client.post("/api/v1/identify/jobs", headers=headers)

    assert first_response.status_code == 422
    assert second_response.status_code == 429
    assert second_response.headers["Retry-After"] == "60"


@pytest.mark.usefixtures("rate_limited_app")
def test_health_endpoints_are_exempt_from_rate_limit() -> None:
    headers = {"x-forwarded-for": "198.51.100.30"}

    with TestClient(app) as client:
        responses = [client.get("/api/v1/health", headers=headers) for _ in range(3)]

    assert [response.status_code for response in responses] == [200, 200, 200]
