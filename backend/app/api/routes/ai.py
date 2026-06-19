from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from starlette.responses import JSONResponse

from app.api.auth_dependencies import AuthenticatedUser, require_authenticated_user
from app.core.config import BACKEND_ROOT, settings
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


class SpotifyImportPathError(ValueError):
    """Raised when a requested Spotify import file is outside the configured import directory."""


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
    current_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    service: Annotated[AiInsightsService, Depends(get_ai_insights_service)],
) -> AiChatResponse | JSONResponse:
    try:
        reply = service.chat(
            db=db,
            user_id=current_user.account.id,
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
    current_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    service: Annotated[AiInsightsService, Depends(get_ai_insights_service)],
    conversation_id: Annotated[str | None, Query(max_length=36)] = None,
) -> AiChatHistoryResponse | JSONResponse:
    try:
        history = service.get_history(db, user_id=current_user.account.id, conversation_id=conversation_id)
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
    current_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    service: Annotated[AiInsightsService, Depends(get_ai_insights_service)],
    conversation_id: Annotated[str | None, Query(max_length=36)] = None,
) -> AiChatClearResponse | JSONResponse:
    try:
        result = service.clear_history(db, user_id=current_user.account.id, conversation_id=conversation_id)
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
    current_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    service: Annotated[AiInsightsService, Depends(get_ai_insights_service)],
    conversation_id: Annotated[str | None, Query(max_length=36)] = None,
) -> AiChatExportResponse | JSONResponse:
    try:
        history = service.export_history(db, user_id=current_user.account.id, conversation_id=conversation_id)
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
    current_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    service: Annotated[SpotifyListeningImportService, Depends(get_spotify_listening_import_service)],
) -> SpotifyListeningImportResponse | JSONResponse:
    try:
        import_root = _spotify_import_root()
        resolved_files = [_resolve_spotify_import_file(import_root, file_path) for file_path in request.file_paths]
        result = service.import_files(
            db,
            resolved_files,
            user_id=current_user.account.id,
            batch_size=request.batch_size,
            refresh_rollups=request.refresh_rollups,
        )
    except SpotifyImportPathError as error:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={"error": {"code": "spotify_import_path_invalid", "message": str(error)}},
        )
    except OSError:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={
                "error": {
                    "code": "spotify_import_failed",
                    "message": "Spotify import file could not be read from the configured import directory.",
                }
            },
        )
    except ValueError:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={
                "error": {
                    "code": "spotify_import_failed",
                    "message": "Spotify import failed while reading configured files.",
                }
            },
        )

    return SpotifyListeningImportResponse(
        batch_id=result.batch_id,
        source_files=request.file_paths,
        total_items=result.total_items,
        imported_count=result.imported_count,
        duplicate_count=result.duplicate_count,
        skipped_count=result.skipped_count,
        error_count=result.error_count,
        error_summary=result.error_summary,
    )


def _spotify_import_root() -> Path:
    configured_root = Path(settings.spotify_import_dir)
    import_root = configured_root if configured_root.is_absolute() else BACKEND_ROOT / configured_root

    if import_root.is_symlink():
        raise SpotifyImportPathError("Spotify import directory must not be a symlink.")

    try:
        resolved_root = import_root.resolve(strict=True)
    except OSError as error:
        raise SpotifyImportPathError("Spotify import directory is not available.") from error

    if not resolved_root.is_dir():
        raise SpotifyImportPathError("Spotify import directory is not a directory.")

    return resolved_root


def _resolve_spotify_import_file(import_root: Path, requested_path: str) -> Path:
    requested_file = Path(requested_path)

    if requested_file.is_absolute() or ".." in requested_file.parts:
        raise SpotifyImportPathError("Spotify import files must be relative to the configured import directory.")

    candidate = import_root / requested_file

    try:
        candidate.relative_to(import_root)
    except ValueError as error:
        raise SpotifyImportPathError("Spotify import file escapes the configured import directory.") from error

    current_path = import_root
    for part in requested_file.parts:
        current_path = current_path / part
        if current_path.is_symlink():
            raise SpotifyImportPathError("Spotify import files must not be symlinks.")

    try:
        resolved_file = candidate.resolve(strict=True)
        resolved_file.relative_to(import_root)
    except OSError as error:
        raise SpotifyImportPathError("Spotify import file was not found in the configured import directory.") from error
    except ValueError as error:
        raise SpotifyImportPathError("Spotify import file escapes the configured import directory.") from error

    if not resolved_file.is_file():
        raise SpotifyImportPathError("Spotify import path is not a file.")

    return resolved_file
