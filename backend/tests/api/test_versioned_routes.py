from fastapi.testclient import TestClient

from app.api.routes.sessions import get_sessions_service
from app.main import app
from app.services.sessions_service import SessionNotFoundError

client = TestClient(app)


def test_releases_route_is_versioned() -> None:
    response = client.get("/api/v1/releases")

    assert response.status_code == 200
    assert response.json() == {"message": "list of releases"}


def test_sessions_route_is_versioned() -> None:
    class StubSessionsService:
        def get_session(self, _db, _session_id: str):
            raise SessionNotFoundError("missing-session")

    app.dependency_overrides[get_sessions_service] = lambda: StubSessionsService()
    response = client.get("/api/v1/sessions/missing-session")
    app.dependency_overrides.clear()

    assert response.status_code == 404


def test_analytics_route_is_versioned() -> None:
    class StubAnalyticsService:
        def get_monthly_plays(self, _db):
            return []

    from app.api.routes.analytics import get_analytics_service

    app.dependency_overrides[get_analytics_service] = lambda: StubAnalyticsService()
    response = client.get("/api/v1/analytics/plays/monthly")
    app.dependency_overrides.clear()

    assert response.status_code == 200


def test_ai_route_is_versioned() -> None:
    class StubAiService:
        def chat(self, *, db, message: str, conversation_id=None, client_context=None):
            _ = db, message, conversation_id, client_context

            class Reply:
                conversation_id = "local-single-thread"
                content = "Hello"
                used_tools = []

            return Reply()

    from app.api.routes.ai import get_ai_insights_service

    app.dependency_overrides[get_ai_insights_service] = lambda: StubAiService()
    response = client.post("/api/v1/ai/chat", json={"message": "Hello"})
    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["conversation_id"] == "local-single-thread"


def test_identify_route_is_versioned() -> None:
    response = client.post("/api/v1/identify")

    assert response.status_code == 422
