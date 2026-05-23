import pytest

from app.services.ai_insights_service import AiInsightsService, AiInsightsValidationError


def test_chat_returns_stub_reply_with_existing_conversation_id() -> None:
    service = AiInsightsService()

    reply = service.chat(
        message="What style did I explore most this month?",
        conversation_id="conversation-123",
        client_context={"timezone": "America/Los_Angeles"},
    )

    assert reply.conversation_id == "conversation-123"
    assert "backend skeleton" in reply.content
    assert reply.used_tools == []


def test_chat_uses_default_single_thread_conversation_id() -> None:
    service = AiInsightsService()

    reply = service.chat(message="Recommend a record from my collection")

    assert reply.conversation_id == AiInsightsService.DEFAULT_CONVERSATION_ID


def test_chat_rejects_blank_message() -> None:
    service = AiInsightsService()

    with pytest.raises(AiInsightsValidationError) as error:
        service.chat(message="   ")

    assert error.value.code == "empty_message"
    assert error.value.message == "message must not be blank."


def test_chat_rejects_blank_conversation_id() -> None:
    service = AiInsightsService()

    with pytest.raises(AiInsightsValidationError) as error:
        service.chat(message="Hello", conversation_id="   ")

    assert error.value.code == "empty_conversation_id"
    assert error.value.message == "conversation_id must not be blank when provided."
