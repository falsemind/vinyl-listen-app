from fastapi.testclient import TestClient

from app.api.routes import health
from app.core.runtime_dependencies import RuntimeDependencyStatus
from app.main import app

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_runtime_health_endpoint_reports_required_dependency_readiness(monkeypatch) -> None:
    monkeypatch.setattr(
        health,
        "get_runtime_dependency_statuses",
        lambda: (
            RuntimeDependencyStatus(
                name="mlx_vlm_service",
                available=False,
                detail="IDENTIFY_MLX_VLM_SERVICE_URL is not configured.",
                warn_when_unavailable=True,
            ),
            RuntimeDependencyStatus(
                name="paddleocr",
                available=False,
                detail="Optional PaddleOCR-VL backend package is not installed.",
                warn_when_unavailable=False,
            ),
        ),
    )
    monkeypatch.setattr(
        health,
        "get_identify_operations_status",
        lambda: {"max_concurrency": 1, "active_jobs": 0, "queued_jobs": None},
    )

    response = client.get("/api/v1/health/runtime")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "degraded"
    assert payload["ready"] is False
    assert payload["dependencies"][0]["required"] is True
    assert payload["dependencies"][1]["required"] is False
    assert payload["operations"]["rate_limiter"] == {
        "enabled": health.settings.inbound_rate_limit_enabled,
        "backend": health.settings.inbound_rate_limit_backend,
    }
    assert payload["operations"]["identify"] == {
        "max_concurrency": 1,
        "active_jobs": 0,
        "queued_jobs": None,
    }


def test_favicon_endpoint_returns_no_content() -> None:
    response = client.get("/favicon.ico")

    assert response.status_code == 204
    assert response.content == b""
