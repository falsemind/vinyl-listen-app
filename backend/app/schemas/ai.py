from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AiChatClientContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timezone: str | None = Field(default=None, min_length=1, max_length=64)


class AiChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conversation_id: str | None = Field(default=None, max_length=36)
    message: str = Field(min_length=1, max_length=4000)
    client_context: AiChatClientContext | None = None


class AiChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    used_tools: list[str] = Field(default_factory=list)
    created_at: datetime | None = None


class AiChatResponse(BaseModel):
    conversation_id: str
    message: AiChatMessage
    used_tools: list[str] = Field(default_factory=list)


class AiChatHistoryResponse(BaseModel):
    conversation_id: str
    messages: list[AiChatMessage] = Field(default_factory=list)


class AiChatClearResponse(BaseModel):
    conversation_id: str
    deleted_messages: int


class AiChatExportResponse(BaseModel):
    conversation_id: str
    exported_at: datetime
    messages: list[AiChatMessage] = Field(default_factory=list)


class SpotifyListeningImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file_paths: list[str] = Field(min_length=1, max_length=8)
    batch_size: int = Field(default=1000, ge=1, le=10000)
    refresh_rollups: bool = True


class SpotifyListeningImportResponse(BaseModel):
    batch_id: str
    source_files: list[str]
    total_items: int
    imported_count: int
    duplicate_count: int
    skipped_count: int
    error_count: int
    error_summary: list[str] = Field(default_factory=list)
