import logging
from dataclasses import dataclass
from time import perf_counter

from app.ai.chat_adapter import (
    AiChatAdapter,
    AiChatAdapterError,
    AiChatAdapterReply,
    build_ai_chat_adapter,
)
from app.core.config import settings

logger = logging.getLogger(__name__)

PROVIDER_UNAVAILABLE_CONTENT = (
    "AI Insights is configured, but the model provider is unavailable right now. "
    "Check the backend AI chat settings and the LM Studio server."
)


class AiInsightsServiceError(Exception):
    """Base error for AI insights service failures."""


class AiInsightsValidationError(AiInsightsServiceError):
    """Raised when AI chat input fails validation."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


@dataclass(frozen=True)
class AiInsightsReply:
    conversation_id: str
    content: str
    used_tools: list[str]


class AiInsightsService:
    DEFAULT_CONVERSATION_ID = "local-single-thread"

    def __init__(self, adapter: AiChatAdapter | None = None) -> None:
        self.adapter = adapter or build_ai_chat_adapter(settings)

    def chat(
        self,
        *,
        message: str,
        conversation_id: str | None = None,
        client_context: dict[str, str] | None = None,
    ) -> AiInsightsReply:
        cleaned_message = message.strip()
        if not cleaned_message:
            raise AiInsightsValidationError("empty_message", "message must not be blank.")

        cleaned_conversation_id = self._conversation_id(conversation_id)
        started_at = perf_counter()

        try:
            adapter_reply = self.adapter.generate_reply(
                message=cleaned_message,
                conversation_id=cleaned_conversation_id,
                client_context=client_context,
            )
        except AiChatAdapterError:
            elapsed_ms = (perf_counter() - started_at) * 1000
            logger.warning(
                "AI insights provider failure provider=%s elapsed_ms=%.2f",
                self.adapter.provider_name,
                elapsed_ms,
                exc_info=True,
            )
            adapter_reply = AiChatAdapterReply(content=PROVIDER_UNAVAILABLE_CONTENT, used_tools=[])
        else:
            elapsed_ms = (perf_counter() - started_at) * 1000
            logger.info(
                "AI insights reply generated provider=%s elapsed_ms=%.2f used_tools=%s",
                self.adapter.provider_name,
                elapsed_ms,
                adapter_reply.used_tools,
            )

        return AiInsightsReply(
            conversation_id=cleaned_conversation_id,
            content=adapter_reply.content,
            used_tools=adapter_reply.used_tools,
        )

    def _conversation_id(self, conversation_id: str | None) -> str:
        if conversation_id is None:
            return self.DEFAULT_CONVERSATION_ID

        cleaned_conversation_id = conversation_id.strip()
        if not cleaned_conversation_id:
            raise AiInsightsValidationError(
                "empty_conversation_id",
                "conversation_id must not be blank when provided.",
            )
        return cleaned_conversation_id
