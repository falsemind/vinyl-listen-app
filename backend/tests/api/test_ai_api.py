from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.api.routes.ai import get_ai_insights_service, get_spotify_listening_import_service
from app.database.session import get_db
from app.main import app
from app.services.ai_insights_service import (
    AiInsightsClearResult,
    AiInsightsHistory,
    AiInsightsHistoryMessage,
    AiInsightsReply,
    AiInsightsValidationError,
)
from app.services.spotify_listening_import_service import SpotifyListeningImportResult


@pytest.fixture(autouse=True)
def clear_dependency_overrides() -> None:
    yield
    app.dependency_overrides.clear()


class StubAiInsightsService:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []
        self.error: AiInsightsValidationError | None = None

    def chat(
        self,
        *,
        db: object,
        message: str,
        conversation_id: str | None = None,
        client_context: dict[str, str] | None = None,
    ) -> AiInsightsReply:
        _ = db
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

    def get_history(
        self,
        db: object,
        *,
        conversation_id: str | None = None,
    ) -> AiInsightsHistory:
        _ = db
        return AiInsightsHistory(
            conversation_id=conversation_id or "local-single-thread",
            messages=[
                AiInsightsHistoryMessage(
                    role="user",
                    content="Stored question",
                    used_tools=[],
                    created_at=datetime(2026, 5, 23, 12, 0, tzinfo=UTC),
                ),
                AiInsightsHistoryMessage(
                    role="assistant",
                    content="Stored answer",
                    used_tools=["history"],
                    created_at=datetime(2026, 5, 23, 12, 1, tzinfo=UTC),
                ),
            ],
        )

    def clear_history(
        self,
        db: object,
        *,
        conversation_id: str | None = None,
    ) -> AiInsightsClearResult:
        _ = db
        return AiInsightsClearResult(conversation_id=conversation_id or "local-single-thread", deleted_messages=2)

    def export_history(
        self,
        db: object,
        *,
        conversation_id: str | None = None,
    ) -> AiInsightsHistory:
        return self.get_history(db, conversation_id=conversation_id)


class StubSpotifyListeningImportService:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def import_files(
        self,
        db: object,
        file_paths: list[str],
        *,
        batch_size: int,
        refresh_rollups: bool,
    ) -> SpotifyListeningImportResult:
        _ = db
        self.calls.append(
            {
                "file_paths": file_paths,
                "batch_size": batch_size,
                "refresh_rollups": refresh_rollups,
            }
        )
        return SpotifyListeningImportResult(
            batch_id="spotify-batch-1",
            source_paths=file_paths,
            total_items=3,
            imported_count=2,
            duplicate_count=1,
            skipped_count=0,
            error_count=0,
            error_summary=[],
        )


def test_chat_endpoint_returns_stub_response_and_forwards_request() -> None:
    service = StubAiInsightsService()
    app.dependency_overrides[get_ai_insights_service] = lambda: service
    app.dependency_overrides[get_db] = lambda: object()

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
        "message": {"role": "assistant", "content": "Stub AI response", "used_tools": [], "created_at": None},
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
    app.dependency_overrides[get_db] = lambda: object()

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


def test_chat_endpoint_rejects_unknown_client_context_fields() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/ai/chat",
            json={
                "message": "What should I listen to?",
                "client_context": {"timezone": "America/Los_Angeles", "large_blob": "x"},
            },
        )

    assert response.status_code == 422


def test_chat_endpoint_rejects_oversized_client_context_value() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/ai/chat",
            json={
                "message": "What should I listen to?",
                "client_context": {"timezone": "x" * 65},
            },
        )

    assert response.status_code == 422


def test_chat_history_endpoint_returns_persisted_messages() -> None:
    service = StubAiInsightsService()
    app.dependency_overrides[get_ai_insights_service] = lambda: service
    app.dependency_overrides[get_db] = lambda: object()

    with TestClient(app) as client:
        response = client.get("/api/v1/ai/chat/history?conversation_id=conversation-123")

    assert response.status_code == 200
    assert response.json()["conversation_id"] == "conversation-123"
    assert [message["role"] for message in response.json()["messages"]] == ["user", "assistant"]


def test_chat_export_endpoint_returns_persisted_messages() -> None:
    service = StubAiInsightsService()
    app.dependency_overrides[get_ai_insights_service] = lambda: service
    app.dependency_overrides[get_db] = lambda: object()

    with TestClient(app) as client:
        response = client.get("/api/v1/ai/chat/export")

    assert response.status_code == 200
    assert response.json()["conversation_id"] == "local-single-thread"
    assert response.json()["exported_at"]
    assert len(response.json()["messages"]) == 2


def test_chat_history_delete_endpoint_returns_deleted_count() -> None:
    service = StubAiInsightsService()
    app.dependency_overrides[get_ai_insights_service] = lambda: service
    app.dependency_overrides[get_db] = lambda: object()

    with TestClient(app) as client:
        response = client.delete("/api/v1/ai/chat/history")

    assert response.status_code == 200
    assert response.json() == {"conversation_id": "local-single-thread", "deleted_messages": 2}


def test_chat_history_endpoint_rejects_long_conversation_id() -> None:
    service = StubAiInsightsService()
    app.dependency_overrides[get_ai_insights_service] = lambda: service
    app.dependency_overrides[get_db] = lambda: object()

    with TestClient(app) as client:
        response = client.get(f"/api/v1/ai/chat/history?conversation_id={'x' * 37}")

    assert response.status_code == 422


def test_spotify_import_endpoint_returns_import_counts() -> None:
    service = StubSpotifyListeningImportService()
    app.dependency_overrides[get_spotify_listening_import_service] = lambda: service
    app.dependency_overrides[get_db] = lambda: object()

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/ai/spotify/import",
            json={
                "file_paths": ["/data/spotify/Streaming_History_Audio_2019.json"],
                "batch_size": 500,
                "refresh_rollups": True,
            },
        )

    assert response.status_code == 200
    assert service.calls == [
        {
            "file_paths": ["/data/spotify/Streaming_History_Audio_2019.json"],
            "batch_size": 500,
            "refresh_rollups": True,
        }
    ]
    assert response.json() == {
        "batch_id": "spotify-batch-1",
        "source_paths": ["/data/spotify/Streaming_History_Audio_2019.json"],
        "total_items": 3,
        "imported_count": 2,
        "duplicate_count": 1,
        "skipped_count": 0,
        "error_count": 0,
        "error_summary": [],
    }
