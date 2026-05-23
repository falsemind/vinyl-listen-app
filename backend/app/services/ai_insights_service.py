from dataclasses import dataclass


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
        _ = client_context

        return AiInsightsReply(
            conversation_id=cleaned_conversation_id,
            content=(
                "AI Insights received your question. This backend skeleton is ready for "
                "a ChatOpenAI-compatible agent and will answer from known collection data "
                "once the agent runtime is connected."
            ),
            used_tools=[],
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
