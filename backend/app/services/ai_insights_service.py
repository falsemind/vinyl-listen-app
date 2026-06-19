import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from time import perf_counter

from sqlalchemy.orm import Session

from app.ai.chat_adapter import (
    AiChatAdapter,
    AiChatAdapterError,
    AiChatAdapterReply,
    AiChatHistoryMessage,
    build_ai_chat_adapter,
)
from app.ai.insight_tools import AiInsightToolRunner
from app.core.config import settings
from app.models.ai_chat import AiChatMessageRecord
from app.repositories.ai_chat_repository import AiChatRepository

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


@dataclass(frozen=True)
class AiInsightsHistoryMessage:
    role: str
    content: str
    used_tools: list[str]
    created_at: datetime


@dataclass(frozen=True)
class AiInsightsHistory:
    conversation_id: str
    messages: list[AiInsightsHistoryMessage]


@dataclass(frozen=True)
class AiInsightsClearResult:
    conversation_id: str
    deleted_messages: int


class AiInsightsService:
    DEFAULT_CONVERSATION_ID = "local-single-thread"
    MAX_PROMPT_HISTORY_MESSAGES = 20

    def __init__(
        self,
        adapter: AiChatAdapter | None = None,
        repository: AiChatRepository | None = None,
        tool_runner: AiInsightToolRunner | None = None,
    ) -> None:
        self.adapter = adapter or build_ai_chat_adapter(settings)
        self.repository = repository or AiChatRepository()
        self.tool_runner = tool_runner or AiInsightToolRunner()

    def chat(
        self,
        *,
        db: Session,
        user_id: str,
        message: str,
        conversation_id: str | None = None,
        client_context: dict[str, str] | None = None,
    ) -> AiInsightsReply:
        cleaned_message = message.strip()
        if not cleaned_message:
            raise AiInsightsValidationError("empty_message", "message must not be blank.")

        cleaned_conversation_id = self._conversation_id(conversation_id)
        started_at = perf_counter()
        prompt_history = [
            AiChatHistoryMessage(role=message_record.role, content=message_record.content)
            for message_record in self.repository.list_messages(
                db,
                cleaned_conversation_id,
                user_id=user_id,
                limit=self.MAX_PROMPT_HISTORY_MESSAGES,
            )
            if message_record.role in {"user", "assistant"}
        ]
        tool_context = self.tool_runner.run(db, user_id=user_id, message=cleaned_message)
        used_tool_names = [result.name for result in tool_context]

        try:
            adapter_reply = self.adapter.generate_reply(
                message=cleaned_message,
                conversation_id=cleaned_conversation_id,
                client_context=client_context,
                history=prompt_history,
                tool_context=tool_context,
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
                used_tool_names + adapter_reply.used_tools,
            )
        response_used_tools = used_tool_names + [
            tool_name for tool_name in adapter_reply.used_tools if tool_name not in used_tool_names
        ]

        self.repository.append_turn(
            db,
            user_id=user_id,
            conversation_id=cleaned_conversation_id,
            user_content=cleaned_message,
            assistant_content=adapter_reply.content,
            used_tools=response_used_tools,
            client_context=client_context,
        )
        return AiInsightsReply(
            conversation_id=cleaned_conversation_id,
            content=adapter_reply.content,
            used_tools=response_used_tools,
        )

    def get_history(
        self,
        db: Session,
        *,
        user_id: str,
        conversation_id: str | None = None,
    ) -> AiInsightsHistory:
        cleaned_conversation_id = self._conversation_id(conversation_id)
        messages = self.repository.list_messages(db, cleaned_conversation_id, user_id=user_id)
        return AiInsightsHistory(
            conversation_id=cleaned_conversation_id,
            messages=[self._history_message(message_record) for message_record in messages],
        )

    def clear_history(
        self,
        db: Session,
        *,
        user_id: str,
        conversation_id: str | None = None,
    ) -> AiInsightsClearResult:
        cleaned_conversation_id = self._conversation_id(conversation_id)
        deleted_messages = self.repository.delete_conversation(
            db,
            user_id=user_id,
            conversation_id=cleaned_conversation_id,
        )
        return AiInsightsClearResult(
            conversation_id=cleaned_conversation_id,
            deleted_messages=deleted_messages,
        )

    def export_history(
        self,
        db: Session,
        *,
        user_id: str,
        conversation_id: str | None = None,
    ) -> AiInsightsHistory:
        return self.get_history(db, user_id=user_id, conversation_id=conversation_id)

    def _conversation_id(self, conversation_id: str | None) -> str:
        if conversation_id is None:
            return self.DEFAULT_CONVERSATION_ID

        cleaned_conversation_id = conversation_id.strip()
        if not cleaned_conversation_id:
            raise AiInsightsValidationError(
                "empty_conversation_id",
                "conversation_id must not be blank when provided.",
            )
        if len(cleaned_conversation_id) > 36:
            raise AiInsightsValidationError(
                "invalid_conversation_id",
                "conversation_id must be 36 characters or fewer.",
            )
        return cleaned_conversation_id

    def _history_message(self, message_record: AiChatMessageRecord) -> AiInsightsHistoryMessage:
        return AiInsightsHistoryMessage(
            role=message_record.role,
            content=message_record.content,
            used_tools=message_record.used_tools or [],
            created_at=message_record.created_at or datetime.now(UTC),
        )
