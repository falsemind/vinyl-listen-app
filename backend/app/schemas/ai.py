from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AiChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conversation_id: str | None = None
    message: str = Field(min_length=1, max_length=4000)
    client_context: dict[str, str] | None = None


class AiChatMessage(BaseModel):
    role: Literal["assistant"]
    content: str


class AiChatResponse(BaseModel):
    conversation_id: str
    message: AiChatMessage
    used_tools: list[str] = Field(default_factory=list)
