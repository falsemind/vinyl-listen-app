from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from starlette.responses import JSONResponse

from app.database.session import get_db
from app.schemas.ai import (
    AiChatClearResponse,
    AiChatExportResponse,
    AiChatHistoryResponse,
    AiChatMessage,
    AiChatRequest,
    AiChatResponse,
    SpotifyListeningImportRequest,
    SpotifyListeningImportResponse,
)
from app.schemas.sessions import ErrorResponse
from app.services.ai_insights_service import AiInsightsService, AiInsightsValidationError
from app.services.spotify_listening_import_service import SpotifyListeningImportService

router = APIRouter()


def get_ai_insights_service() -> AiInsightsService:
    return AiInsightsService()


def get_spotify_listening_import_service() -> SpotifyListeningImportService:
    return SpotifyListeningImportService()


@router.post(
    "/chat",
    response_model=AiChatResponse,
    responses={422: {"model": ErrorResponse}},
)
def chat(
    request: AiChatRequest,
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[AiInsightsService, Depends(get_ai_insights_service)],
) -> AiChatResponse | JSONResponse:
    try:
        reply = service.chat(
            db=db,
            message=request.message,
            conversation_id=request.conversation_id,
            client_context=request.client_context.model_dump(exclude_none=True) if request.client_context else None,
        )
    except AiInsightsValidationError as error:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={"error": {"code": error.code, "message": error.message}},
        )

    return AiChatResponse(
        conversation_id=reply.conversation_id,
        message=AiChatMessage(role="assistant", content=reply.content),
        used_tools=reply.used_tools,
    )


@router.get(
    "/chat/history",
    response_model=AiChatHistoryResponse,
    responses={422: {"model": ErrorResponse}},
)
def get_chat_history(
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[AiInsightsService, Depends(get_ai_insights_service)],
    conversation_id: Annotated[str | None, Query(max_length=36)] = None,
) -> AiChatHistoryResponse | JSONResponse:
    try:
        history = service.get_history(db, conversation_id=conversation_id)
    except AiInsightsValidationError as error:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={"error": {"code": error.code, "message": error.message}},
        )
    return AiChatHistoryResponse(
        conversation_id=history.conversation_id,
        messages=[
            AiChatMessage(
                role=message.role,
                content=message.content,
                used_tools=message.used_tools,
                created_at=message.created_at,
            )
            for message in history.messages
        ],
    )


@router.delete(
    "/chat/history",
    response_model=AiChatClearResponse,
    responses={422: {"model": ErrorResponse}},
)
def clear_chat_history(
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[AiInsightsService, Depends(get_ai_insights_service)],
    conversation_id: Annotated[str | None, Query(max_length=36)] = None,
) -> AiChatClearResponse | JSONResponse:
    try:
        result = service.clear_history(db, conversation_id=conversation_id)
    except AiInsightsValidationError as error:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={"error": {"code": error.code, "message": error.message}},
        )
    return AiChatClearResponse(
        conversation_id=result.conversation_id,
        deleted_messages=result.deleted_messages,
    )


@router.get(
    "/chat/export",
    response_model=AiChatExportResponse,
    responses={422: {"model": ErrorResponse}},
)
def export_chat_history(
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[AiInsightsService, Depends(get_ai_insights_service)],
    conversation_id: Annotated[str | None, Query(max_length=36)] = None,
) -> AiChatExportResponse | JSONResponse:
    try:
        history = service.export_history(db, conversation_id=conversation_id)
    except AiInsightsValidationError as error:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={"error": {"code": error.code, "message": error.message}},
        )
    return AiChatExportResponse(
        conversation_id=history.conversation_id,
        exported_at=datetime.now(UTC),
        messages=[
            AiChatMessage(
                role=message.role,
                content=message.content,
                used_tools=message.used_tools,
                created_at=message.created_at,
            )
            for message in history.messages
        ],
    )


@router.post(
    "/spotify/import",
    response_model=SpotifyListeningImportResponse,
    responses={422: {"model": ErrorResponse}},
)
def import_spotify_listening_history(
    request: SpotifyListeningImportRequest,
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[SpotifyListeningImportService, Depends(get_spotify_listening_import_service)],
) -> SpotifyListeningImportResponse | JSONResponse:
    try:
        result = service.import_files(
            db,
            request.file_paths,
            batch_size=request.batch_size,
            refresh_rollups=request.refresh_rollups,
        )
    except (OSError, ValueError) as error:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={"error": {"code": "spotify_import_failed", "message": str(error)}},
        )

    return SpotifyListeningImportResponse(
        batch_id=result.batch_id,
        source_paths=result.source_paths,
        total_items=result.total_items,
        imported_count=result.imported_count,
        duplicate_count=result.duplicate_count,
        skipped_count=result.skipped_count,
        error_count=result.error_count,
        error_summary=result.error_summary,
    )
