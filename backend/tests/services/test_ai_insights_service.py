import pytest

from app.ai.chat_adapter import AiChatAdapterError, AiChatAdapterReply
from app.services.ai_insights_service import (
    PROVIDER_UNAVAILABLE_CONTENT,
    AiInsightsService,
    AiInsightsValidationError,
)


class StubAiChatAdapter:
    provider_name = "stub"
    calls: list[dict[str, object]]
    error: AiChatAdapterError | None

    def __init__(self, reply: AiChatAdapterReply | None = None) -> None:
        self.calls = []
        self.error = None
        self.reply = reply or AiChatAdapterReply(content="Adapter response", used_tools=[])

    def generate_reply(
        self,
        *,
        message: str,
        conversation_id: str,
        client_context: dict[str, str] | None = None,
    ) -> AiChatAdapterReply:
        self.calls.append(
            {
                "message": message,
                "conversation_id": conversation_id,
                "client_context": client_context,
            }
        )
        if self.error is not None:
            raise self.error
        return self.reply


def test_chat_returns_adapter_reply_with_existing_conversation_id() -> None:
    adapter = StubAiChatAdapter(reply=AiChatAdapterReply(content="You explored ambient most.", used_tools=["summary"]))
    service = AiInsightsService(adapter=adapter)

    reply = service.chat(
        message="  What style did I explore most this month?  ",
        conversation_id="conversation-123",
        client_context={"timezone": "America/Los_Angeles"},
    )

    assert reply.conversation_id == "conversation-123"
    assert reply.content == "You explored ambient most."
    assert reply.used_tools == ["summary"]
    assert adapter.calls == [
        {
            "message": "What style did I explore most this month?",
            "conversation_id": "conversation-123",
            "client_context": {"timezone": "America/Los_Angeles"},
        }
    ]


def test_chat_uses_default_single_thread_conversation_id() -> None:
    adapter = StubAiChatAdapter()
    service = AiInsightsService(adapter=adapter)

    reply = service.chat(message="Recommend a record from my collection")

    assert reply.conversation_id == AiInsightsService.DEFAULT_CONVERSATION_ID
    assert adapter.calls[0]["conversation_id"] == AiInsightsService.DEFAULT_CONVERSATION_ID


def test_chat_returns_safe_reply_when_adapter_fails() -> None:
    adapter = StubAiChatAdapter()
    adapter.error = AiChatAdapterError("provider unavailable")
    service = AiInsightsService(adapter=adapter)

    reply = service.chat(message="What should I listen to?")

    assert reply.content == PROVIDER_UNAVAILABLE_CONTENT
    assert reply.used_tools == []


def test_chat_rejects_blank_message() -> None:
    service = AiInsightsService(adapter=StubAiChatAdapter())

    with pytest.raises(AiInsightsValidationError) as error:
        service.chat(message="   ")

    assert error.value.code == "empty_message"
    assert error.value.message == "message must not be blank."


def test_chat_rejects_blank_conversation_id() -> None:
    service = AiInsightsService(adapter=StubAiChatAdapter())

    with pytest.raises(AiInsightsValidationError) as error:
        service.chat(message="Hello", conversation_id="   ")

    assert error.value.code == "empty_conversation_id"
    assert error.value.message == "conversation_id must not be blank when provided."
