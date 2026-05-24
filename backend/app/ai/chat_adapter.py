import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Literal, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from app.core.config import Settings

DISABLED_AI_CHAT_CONTENT = (
    "AI Insights is ready, but no model provider is configured yet. "
    "Set the backend AI chat settings to connect an LM Studio or OpenAI-compatible runtime."
)

SYSTEM_PROMPT = (
    "You are the Vinyl Listen AI Insights assistant. Answer only from the user's known vinyl collection, "
    "listening history, ratings, moods, and style data that the backend tools provide. Be transparent when "
    "data is unavailable or sparse. Do not recommend records outside the user's collection."
)


class AiChatAdapterError(Exception):
    """Raised when a configured AI chat adapter cannot produce a reply."""


@dataclass(frozen=True)
class AiChatAdapterReply:
    content: str
    used_tools: list[str]


@dataclass(frozen=True)
class AiChatHistoryMessage:
    role: Literal["user", "assistant"]
    content: str


@dataclass(frozen=True)
class AiChatToolResult:
    name: str
    content: str


class AiChatAdapter(Protocol):
    provider_name: str

    def generate_reply(
        self,
        *,
        message: str,
        conversation_id: str,
        client_context: dict[str, str] | None = None,
        history: Sequence[AiChatHistoryMessage] | None = None,
        tool_context: Sequence[AiChatToolResult] | None = None,
    ) -> AiChatAdapterReply:
        """Generate an assistant reply for a single chat turn."""


@dataclass(frozen=True)
class DisabledAiChatAdapter:
    provider_name: str = "disabled"
    disabled_reason: str = "not_configured"

    def generate_reply(
        self,
        *,
        message: str,
        conversation_id: str,
        client_context: dict[str, str] | None = None,
        history: Sequence[AiChatHistoryMessage] | None = None,
        tool_context: Sequence[AiChatToolResult] | None = None,
    ) -> AiChatAdapterReply:
        _ = message, conversation_id, client_context, history, tool_context
        return AiChatAdapterReply(content=DISABLED_AI_CHAT_CONTENT, used_tools=[])


@dataclass(frozen=True)
class OpenAiCompatibleChatAdapter:
    base_url: str
    endpoint_path: str
    model: str
    api_key: str | None = field(default=None, repr=False)
    timeout_seconds: float = 30.0
    temperature: float = 0.2
    provider_name: str = "openai-compatible"

    def generate_reply(
        self,
        *,
        message: str,
        conversation_id: str,
        client_context: dict[str, str] | None = None,
        history: Sequence[AiChatHistoryMessage] | None = None,
        tool_context: Sequence[AiChatToolResult] | None = None,
    ) -> AiChatAdapterReply:
        _ = conversation_id, client_context
        payload = self._payload(message, history or [], tool_context or [])
        request = Request(
            self._chat_url(),
            data=json.dumps(payload).encode("utf-8"),
            headers=self._headers(),
            method="POST",
        )

        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                response_body = response.read().decode("utf-8")
        except HTTPError as error:
            raise AiChatAdapterError(f"AI provider returned HTTP {error.code}") from error
        except URLError as error:
            raise AiChatAdapterError("AI provider could not be reached") from error
        except TimeoutError as error:
            raise AiChatAdapterError("AI provider timed out") from error

        return AiChatAdapterReply(content=self._extract_content(response_body), used_tools=[])

    def _payload(
        self,
        message: str,
        history: Sequence[AiChatHistoryMessage],
        tool_context: Sequence[AiChatToolResult],
    ) -> dict[str, object]:
        if self._uses_lm_studio_native_chat():
            return {
                "model": self.model,
                "input": self._native_input(message, history, tool_context),
                "temperature": self.temperature,
                "stream": False,
            }

        return {
            "model": self.model,
            "messages": self._openai_messages(message, history, tool_context),
            "temperature": self.temperature,
            "stream": False,
        }

    def _native_input(
        self,
        message: str,
        history: Sequence[AiChatHistoryMessage],
        tool_context: Sequence[AiChatToolResult],
    ) -> str:
        tool_context_block = self._tool_context_block(tool_context)
        history_block = "\n".join(f"{item.role}: {item.content}" for item in history).strip()
        if not history_block:
            return f"{SYSTEM_PROMPT}\n\n{tool_context_block}\n\nUser question: {message}"
        return (
            f"{SYSTEM_PROMPT}\n\n{tool_context_block}\n\n"
            f"Conversation history:\n{history_block}\n\nUser question: {message}"
        )

    def _openai_messages(
        self,
        message: str,
        history: Sequence[AiChatHistoryMessage],
        tool_context: Sequence[AiChatToolResult],
    ) -> list[dict[str, str]]:
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages.append({"role": "system", "content": self._tool_context_block(tool_context)})
        messages.extend({"role": item.role, "content": item.content} for item in history)
        messages.append({"role": "user", "content": message})
        return messages

    def _tool_context_block(self, tool_context: Sequence[AiChatToolResult]) -> str:
        if not tool_context:
            return "Backend collection data: no tool results were provided for this turn."
        rendered_tools = "\n\n".join(f"[{result.name}]\n{result.content}" for result in tool_context)
        return f"Backend collection data from read-only tools:\n{rendered_tools}"

    def _chat_url(self) -> str:
        base_url = self.base_url.rstrip("/") + "/"
        endpoint_path = self.endpoint_path.lstrip("/")
        return urljoin(base_url, endpoint_path)

    def _uses_lm_studio_native_chat(self) -> bool:
        return self.endpoint_path.rstrip("/") == "/api/v1/chat"

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _extract_content(self, response_body: str) -> str:
        try:
            decoded = json.loads(response_body)
        except json.JSONDecodeError as error:
            raise AiChatAdapterError("AI provider response did not include assistant content") from error

        content = self._extract_openai_content(decoded) or self._extract_lm_studio_content(decoded)
        if not isinstance(content, str) or not content.strip():
            raise AiChatAdapterError("AI provider response content was empty")
        return content.strip()

    def _extract_openai_content(self, decoded: object) -> str | None:
        if not isinstance(decoded, dict):
            return None
        choices = decoded.get("choices")
        if not isinstance(choices, list) or not choices:
            return None
        first_choice = choices[0]
        if not isinstance(first_choice, dict):
            return None
        message = first_choice.get("message")
        if isinstance(message, dict):
            content = message.get("content")
            return content if isinstance(content, str) else None
        text = first_choice.get("text")
        return text if isinstance(text, str) else None

    def _extract_lm_studio_content(self, decoded: object) -> str | None:
        if not isinstance(decoded, dict):
            return None
        output = decoded.get("output")
        if isinstance(output, list):
            for item in output:
                if isinstance(item, dict) and item.get("type") == "message":
                    content = item.get("content")
                    if isinstance(content, str):
                        return content
        message = decoded.get("message")
        if isinstance(message, dict):
            content = message.get("content")
            return content if isinstance(content, str) else None
        for key in ("content", "response", "text"):
            content = decoded.get(key)
            if isinstance(content, str):
                return content
        return None


def build_ai_chat_adapter(settings: Settings) -> AiChatAdapter:
    if not settings.ai_chat_enabled:
        return DisabledAiChatAdapter(disabled_reason="disabled")

    base_url = _clean_optional_string(settings.ai_chat_base_url)
    model = _clean_optional_string(settings.ai_chat_model)
    if base_url is None or model is None:
        return DisabledAiChatAdapter(disabled_reason="missing_provider_config")

    return OpenAiCompatibleChatAdapter(
        base_url=base_url,
        endpoint_path=settings.ai_chat_endpoint_path,
        model=model,
        api_key=_clean_optional_string(settings.ai_chat_api_key),
        timeout_seconds=settings.ai_chat_timeout_seconds,
        temperature=settings.ai_chat_temperature,
    )


def _clean_optional_string(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned_value = value.strip()
    return cleaned_value or None
