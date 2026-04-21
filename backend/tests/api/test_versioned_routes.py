from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_releases_route_is_versioned() -> None:
    response = client.get("/api/v1/releases")

    assert response.status_code == 200
    assert response.json() == {"message": "list of releases"}


def test_sessions_route_is_versioned() -> None:
    response = client.get("/api/v1/sessions/missing-session")

    assert response.status_code == 404


def test_analytics_route_is_versioned() -> None:
    response = client.get("/api/v1/analytics")

    assert response.status_code == 200
    assert response.json() == {"message": "Some analytics insight"}
