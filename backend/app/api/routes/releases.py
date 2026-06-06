import logging
from functools import lru_cache
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.releases import ReleaseImportRequest, ReleaseImportResponse, ReleaseResponse, ReleaseSearchResponse
from app.schemas.sessions import ErrorResponse, ReleaseSessionHistoryItem, ReleaseSessionsResponse
from app.services.discogs_service import DiscogsClientError, DiscogsService
from app.services.release_import_service import ReleaseImportService
from app.services.sessions_service import ReleaseNotFoundError, SessionsService, SessionValidationError
from app.utils.discogs_display import clean_discogs_artist_name

logger = logging.getLogger(__name__)
router = APIRouter()


def get_release_import_service() -> ReleaseImportService:
    return ReleaseImportService()


@lru_cache(maxsize=1)
def get_discogs_service() -> DiscogsService:
    return DiscogsService()


def get_sessions_service() -> SessionsService:
    return SessionsService()


@router.get("/")
def releases():
    logger.info("Releases endpoint called")

    return {"message": "list of releases"}


@router.get("/search", response_model=ReleaseSearchResponse, response_model_exclude_none=True)
def search_releases(
    service: Annotated[DiscogsService, Depends(get_discogs_service)],
    artist: str | None = Query(default=None),
    title: str | None = Query(default=None),
    catalog: str | None = Query(default=None),
    barcode: str | None = Query(default=None),
    year: int | None = Query(default=None, ge=1900),
    query: str | None = Query(default=None),
    limit: int = Query(default=10, ge=1, le=25),
    offset: int = Query(default=0, ge=0),
):
    search_fields = (artist, title, catalog, barcode, year, query)
    if not any(field not in (None, "") for field in search_fields):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="At least one search field is required.",
        )

    try:
        payload = service.search_releases(
            artist=artist,
            title=title,
            catalog_number=catalog,
            barcode=barcode,
            year=year,
            query=query,
            limit=limit,
            offset=offset,
        )
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)) from error
    except DiscogsClientError as error:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(error)) from error

    return ReleaseSearchResponse(
        results=[
            result
            for result in (
                _map_discogs_search_result(item, fallback_artist=artist, fallback_title=title)
                for item in payload.get("results", [])
            )
            if result is not None
        ],
        limit=limit,
        offset=offset,
    )


def _map_discogs_search_result(
    item: dict[str, Any],
    *,
    fallback_artist: str | None,
    fallback_title: str | None,
) -> dict[str, Any] | None:
    discogs_release_id = _coerce_int(item.get("id"))
    if discogs_release_id is None:
        return None

    artist, title = _split_discogs_title(str(item.get("title") or ""))
    return {
        "discogs_release_id": discogs_release_id,
        "artist": clean_discogs_artist_name(artist or fallback_artist) or "Unknown Artist",
        "title": title or fallback_title or str(item.get("title") or "Untitled Release"),
        "year": _coerce_int(item.get("year")),
        "label": _first_string(item.get("label")),
        "catalog_number": _first_string(item.get("catno")),
        "thumbnail_url": item.get("thumb") or item.get("cover_image"),
        "format": _format_release_format(item.get("format")),
    }


def _split_discogs_title(value: str) -> tuple[str | None, str | None]:
    if " - " not in value:
        return None, value or None

    artist, title = value.split(" - ", 1)
    return artist.strip() or None, title.strip() or None


def _first_string(value: Any) -> str | None:
    if isinstance(value, list):
        return str(value[0]) if value else None
    if value is None:
        return None
    return str(value)


def _format_release_format(value: Any) -> str | None:
    if isinstance(value, list):
        formats = [str(item).strip() for item in value if str(item).strip()]
        return ", ".join(formats) if formats else None
    if value is None:
        return None
    formatted = str(value).strip()
    return formatted or None


def _coerce_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


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

    return _release_response(db, service, release)


@router.post("/{release_id}/refresh", response_model=ReleaseResponse)
def refresh_release(
    release_id: str,
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[ReleaseImportService, Depends(get_release_import_service)],
):
    try:
        result = service.refresh_release(db, release_id)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)) from error
    except DiscogsClientError as error:
        error_message = str(error)
        status_code = status.HTTP_404_NOT_FOUND if "(404)" in error_message else status.HTTP_502_BAD_GATEWAY
        raise HTTPException(status_code=status_code, detail=error_message) from error

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Release '{release_id}' was not found.",
        )

    return _release_response(db, service, result.release)


def _release_response(db: Session, service: ReleaseImportService, release) -> ReleaseResponse:
    available_side_options = service.get_available_side_options(db, release.discogs_release_id)
    available_sides = []
    for option in available_side_options:
        if option.side not in available_sides:
            available_sides.append(option.side)

    return ReleaseResponse.model_validate(release).model_copy(
        update={
            "has_full_discogs_info": service.has_full_discogs_info(db, release.discogs_release_id),
            "available_sides": available_sides,
            "available_side_options": available_side_options,
        }
    )


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
                played_at=session.played_at,
                side=session.vinyl_side,
                rating=session.rating,
                mood=session.mood,
                notes=session.notes.strip() if session.notes and session.notes.strip() else None,
                has_notes=bool(session.notes and session.notes.strip()),
                created_at=session.created_at,
                can_edit=service.can_edit_session(session),
                editable_until=service.editable_until(session),
            )
            for session in sessions
        ]
    )
