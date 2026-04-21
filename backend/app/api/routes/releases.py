import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.releases import ReleaseImportRequest, ReleaseImportResponse, ReleaseResponse
from app.schemas.sessions import ErrorResponse, ReleaseSessionHistoryItem, ReleaseSessionsResponse
from app.services.discogs_service import DiscogsClientError
from app.services.release_import_service import ReleaseImportService
from app.services.sessions_service import ReleaseNotFoundError, SessionsService, SessionValidationError

logger = logging.getLogger(__name__)
router = APIRouter()


def get_release_import_service() -> ReleaseImportService:
    return ReleaseImportService()


def get_sessions_service() -> SessionsService:
    return SessionsService()


@router.get("/")
def releases():
    logger.info("Releases endpoint called")

    return {"message": "list of releases"}


@router.post("/import", response_model=ReleaseImportResponse)
def import_release(
    payload: ReleaseImportRequest,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[ReleaseImportService, Depends(get_release_import_service)],
):
    logger.info("Importing Discogs release %s", payload.discogs_release_id)

    try:
        result = service.import_release(
            db,
            payload.discogs_release_id,
            force_refresh=payload.force_refresh,
        )
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)) from error
    except DiscogsClientError as error:
        error_message = str(error)
        status_code = status.HTTP_404_NOT_FOUND if "(404)" in error_message else status.HTTP_502_BAD_GATEWAY
        raise HTTPException(status_code=status_code, detail=error_message) from error

    response.status_code = status.HTTP_201_CREATED if result.created else status.HTTP_200_OK
    return ReleaseImportResponse(
        release_id=result.release.id,
        discogs_release_id=result.release.discogs_release_id,
        status=result.status,
    )


@router.get("/{release_id}", response_model=ReleaseResponse)
def get_release(
    release_id: str,
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[ReleaseImportService, Depends(get_release_import_service)],
):
    release = service.get_release(db, release_id)
    if release is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Release '{release_id}' was not found.",
        )

    return ReleaseResponse.model_validate(release)


@router.get(
    "/{release_id}/sessions",
    response_model=ReleaseSessionsResponse,
    responses={404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def get_release_sessions(
    release_id: str,
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[SessionsService, Depends(get_sessions_service)],
    limit: int = Query(default=20),
    offset: int = Query(default=0),
):
    try:
        sessions = service.get_sessions_by_release(db, release_id, limit=limit, offset=offset)
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

    return ReleaseSessionsResponse(
        sessions=[
            ReleaseSessionHistoryItem(
                session_id=session.id,
                date=session.played_at.date().isoformat() if session.played_at is not None else None,
                side=session.vinyl_side,
                rating=session.rating,
                mood=session.mood,
                has_notes=bool(session.notes and session.notes.strip()),
            )
            for session in sessions
        ]
    )
