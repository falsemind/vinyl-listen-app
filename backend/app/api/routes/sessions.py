import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.sessions import CreateSessionRequest, ErrorResponse, SessionCreateResponse, SessionResponse
from app.services.sessions_service import (
    ReleaseNotFoundError,
    SessionNotFoundError,
    SessionsService,
    SessionValidationError,
)

logger = logging.getLogger(__name__)
router = APIRouter()


def get_sessions_service() -> SessionsService:
    return SessionsService()


@router.post(
    "/",
    response_model=SessionCreateResponse,
    status_code=status.HTTP_201_CREATED,
    responses={422: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
def log_session(
    payload: CreateSessionRequest,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[SessionsService, Depends(get_sessions_service)],
):
    logger.info("Creating listening session for release %s", payload.release_id)

    try:
        result = service.create_session(
            db,
            release_id=payload.release_id,
            rating=payload.rating,
            mood=payload.mood,
            notes=payload.notes,
            played_at=payload.played_at,
            side=payload.side,
        )
    except SessionValidationError as error:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={"error": {"code": error.code, "message": error.message}},
        )
    except ReleaseNotFoundError as error:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"error": {"code": "release_not_found", "message": str(error)}},
        )

    response.status_code = status.HTTP_201_CREATED
    return SessionCreateResponse(
        session_id=result.session_id,
        timestamp=result.timestamp,
        status=result.status,
    )


@router.get(
    "/{session_id}",
    response_model=SessionResponse,
    responses={404: {"model": ErrorResponse}},
)
def get_session(
    session_id: str,
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[SessionsService, Depends(get_sessions_service)],
):
    try:
        session = service.get_session(db, session_id)
    except SessionNotFoundError as error:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"error": {"code": "session_not_found", "message": str(error)}},
        )

    return SessionResponse.model_validate(session)
