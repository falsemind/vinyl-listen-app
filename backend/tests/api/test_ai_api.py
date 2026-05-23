from fastapi.testclient import TestClient

from app.api.routes.ai import get_ai_insights_service
from app.main import app
from app.services.ai_insights_service import AiInsightsReply, AiInsightsValidationError


class StubAiInsightsService:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []
        self.error: AiInsightsValidationError | None = None

    def chat(
        self,
        *,
        message: str,
        conversation_id: str | None = None,
        client_context: dict[str, str] | None = None,
    ) -> AiInsightsReply:
        self.calls.append(
            {
                "message": message,
                "conversation_id": conversation_id,
                "client_context": client_context,
            }
        )
        if self.error is not None:
            raise self.error
        return AiInsightsReply(
            conversation_id=conversation_id or "local-single-thread",
            content="Stub AI response",
            used_tools=[],
        )


def test_chat_endpoint_returns_stub_response_and_forwards_request() -> None:
    service = StubAiInsightsService()
    app.dependency_overrides[get_ai_insights_service] = lambda: service

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/ai/chat",
            json={
                "conversation_id": "conversation-123",
                "message": "What style did I explore most this month?",
                "client_context": {"timezone": "America/Los_Angeles"},
            },
        )

    assert response.status_code == 200
    assert response.json() == {
        "conversation_id": "conversation-123",
        "message": {"role": "assistant", "content": "Stub AI response"},
        "used_tools": [],
    }
    assert service.calls == [
        {
            "message": "What style did I explore most this month?",
            "conversation_id": "conversation-123",
            "client_context": {"timezone": "America/Los_Angeles"},
        }
    ]


def test_chat_endpoint_returns_service_validation_error() -> None:
    service = StubAiInsightsService()
    service.error = AiInsightsValidationError("empty_message", "message must not be blank.")
    app.dependency_overrides[get_ai_insights_service] = lambda: service

    with TestClient(app) as client:
        response = client.post("/api/v1/ai/chat", json={"message": "   "})

    assert response.status_code == 422
    assert response.json() == {
        "error": {
            "code": "empty_message",
            "message": "message must not be blank.",
        }
    }


def test_chat_endpoint_rejects_missing_message() -> None:
    with TestClient(app) as client:
        response = client.post("/api/v1/ai/chat", json={})

    assert response.status_code == 422
