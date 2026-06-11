import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.sessions import (
    ActiveSessionGroupResponse,
    CreateSessionMoodRequest,
    CreateSessionRequest,
    ErrorResponse,
    FinishSessionGroupRequest,
    HomeRecentSessionItem,
    HomeSummaryResponse,
    HomeTopRecordItem,
    SessionCreateResponse,
    SessionGroupResponse,
    SessionMoodItem,
    SessionMoodResponse,
    SessionMoodsResponse,
    SessionResponse,
    SessionTrackResponse,
    StartSessionGroupRequest,
    UpdateSessionRequest,
)
from app.services.session_groups_service import (
    SessionGroupAlreadyActiveError,
    SessionGroupInactiveError,
    SessionGroupNotFoundError,
    SessionGroupsService,
    SessionGroupValidationError,
)
from app.services.sessions_service import (
    ReleaseNotFoundError,
    SessionEditWindowExpiredError,
    SessionMoodAlreadyExistsError,
    SessionNotFoundError,
    SessionsService,
    SessionValidationError,
)

logger = logging.getLogger(__name__)
router = APIRouter()


def get_sessions_service() -> SessionsService:
    return SessionsService()


def get_session_groups_service() -> SessionGroupsService:
    return SessionGroupsService()


@router.post(
    "/groups",
    response_model=SessionGroupResponse,
    status_code=status.HTTP_201_CREATED,
    responses={409: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def start_session_group(
    payload: StartSessionGroupRequest,
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[SessionGroupsService, Depends(get_session_groups_service)],
):
    try:
        session_group = service.start_session_group(db, title=payload.title, started_at=payload.started_at)
    except SessionGroupAlreadyActiveError as error:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"error": {"code": error.code, "message": error.message}},
        )
    except SessionGroupValidationError as error:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={"error": {"code": error.code, "message": error.message}},
        )

    return _map_session_group_response(session_group)


@router.get(
    "/groups/active",
    response_model=ActiveSessionGroupResponse,
)
def get_active_session_group(
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[SessionGroupsService, Depends(get_session_groups_service)],
):
    session_group = service.get_active_session_group(db)
    return ActiveSessionGroupResponse(
        session_group=_map_session_group_response(session_group) if session_group is not None else None,
    )


@router.get(
    "/groups/{session_group_id}",
    response_model=SessionGroupResponse,
    responses={404: {"model": ErrorResponse}},
)
def get_session_group(
    session_group_id: str,
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[SessionGroupsService, Depends(get_session_groups_service)],
):
    try:
        session_group = service.get_session_group(db, session_group_id)
    except SessionGroupNotFoundError as error:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"error": {"code": "session_group_not_found", "message": str(error)}},
        )

    return _map_session_group_response(session_group)


@router.patch(
    "/groups/{session_group_id}/finish",
    response_model=SessionGroupResponse,
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def finish_session_group(
    session_group_id: str,
    payload: FinishSessionGroupRequest,
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[SessionGroupsService, Depends(get_session_groups_service)],
):
    try:
        session_group = service.finish_session_group(db, session_group_id, ended_at=payload.ended_at)
    except SessionGroupNotFoundError as error:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"error": {"code": "session_group_not_found", "message": str(error)}},
        )
    except SessionGroupInactiveError as error:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"error": {"code": error.code, "message": error.message}},
        )
    except SessionGroupValidationError as error:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={"error": {"code": error.code, "message": error.message}},
        )

    return _map_session_group_response(session_group)


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
            track_positions=payload.track_positions,
            session_group_id=payload.session_group_id,
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
    except SessionGroupNotFoundError as error:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"error": {"code": "session_group_not_found", "message": str(error)}},
        )
    except SessionGroupInactiveError as error:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"error": {"code": error.code, "message": error.message}},
        )

    response.status_code = status.HTTP_201_CREATED
    return SessionCreateResponse(
        session_id=result.session_id,
        timestamp=result.timestamp,
        session_group_id=result.session_group_id,
        status=result.status,
    )


@router.get(
    "/summary",
    response_model=HomeSummaryResponse,
    responses={422: {"model": ErrorResponse}},
)
def get_home_summary(
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[SessionsService, Depends(get_sessions_service)],
    recent_limit: int = Query(default=5),
    top_limit: int = Query(default=3),
):
    try:
        summary = service.get_home_summary(db, recent_limit=recent_limit, top_limit=top_limit)
    except SessionValidationError as error:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={"error": {"code": error.code, "message": error.message}},
        )

    tracks_by_session_id = service.get_tracks_by_session_ids(
        db,
        [item.session.id for item in summary.recent_sessions],
    )

    return HomeSummaryResponse(
        recent_sessions=[
            HomeRecentSessionItem(
                session_id=item.session.id,
                release_id=item.release.id,
                session_group_id=item.session.session_group_id,
                artist=item.release.artist,
                title=item.release.title,
                thumbnail_url=item.release.cover_image_url,
                date=item.session.played_at.date().isoformat() if item.session.played_at is not None else None,
                played_at=item.session.played_at,
                side=item.session.vinyl_side,
                tracks=_map_session_tracks(tracks_by_session_id.get(item.session.id, [])),
                rating=item.session.rating,
                mood=item.session.mood,
                has_notes=bool(item.session.notes and item.session.notes.strip()),
                created_at=item.session.created_at,
                can_edit=service.can_edit_session(item.session),
                editable_until=service.editable_until(item.session),
            )
            for item in summary.recent_sessions
        ],
        total_sessions=summary.total_sessions,
        records_this_month=summary.records_this_month,
        top_records=[
            HomeTopRecordItem(
                release_id=item.release.id,
                artist=item.release.artist,
                title=item.release.title,
                thumbnail_url=item.release.cover_image_url,
                plays=item.plays,
                average_rating=round(item.average_rating, 1) if item.average_rating is not None else None,
            )
            for item in summary.top_records
        ],
    )


@router.get(
    "/moods",
    response_model=SessionMoodsResponse,
)
def list_custom_moods(
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[SessionsService, Depends(get_sessions_service)],
):
    moods = service.list_custom_moods(db)
    return SessionMoodsResponse(
        moods=[SessionMoodItem(name=mood.name, is_custom=mood.is_custom) for mood in moods],
    )


@router.post(
    "/moods",
    response_model=SessionMoodResponse,
    status_code=status.HTTP_201_CREATED,
    responses={409: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def create_custom_mood(
    payload: CreateSessionMoodRequest,
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[SessionsService, Depends(get_sessions_service)],
):
    try:
        mood = service.create_custom_mood(db, payload.name)
    except SessionValidationError as error:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={"error": {"code": error.code, "message": error.message}},
        )
    except SessionMoodAlreadyExistsError as error:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"error": {"code": error.code, "message": error.message}},
        )

    return SessionMoodResponse(mood=SessionMoodItem(name=mood.name, is_custom=mood.is_custom))


@router.delete(
    "/moods/{mood_name}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={422: {"model": ErrorResponse}},
)
def delete_custom_mood(
    mood_name: str,
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[SessionsService, Depends(get_sessions_service)],
):
    try:
        service.delete_custom_mood(db, mood_name)
    except SessionValidationError as error:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={"error": {"code": error.code, "message": error.message}},
        )

    return Response(status_code=status.HTTP_204_NO_CONTENT)


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

    return _map_session_response(db, session, service)


@router.patch(
    "/{session_id}",
    response_model=SessionResponse,
    responses={403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def update_session(
    session_id: str,
    payload: UpdateSessionRequest,
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[SessionsService, Depends(get_sessions_service)],
):
    try:
        session = service.update_session(
            db,
            session_id=session_id,
            fields=payload.model_dump(exclude_unset=True),
        )
    except SessionValidationError as error:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={"error": {"code": error.code, "message": error.message}},
        )
    except SessionEditWindowExpiredError as error:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"error": {"code": error.code, "message": error.message}},
        )
    except SessionNotFoundError as error:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"error": {"code": "session_not_found", "message": str(error)}},
        )
    except ReleaseNotFoundError as error:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"error": {"code": "release_not_found", "message": str(error)}},
        )

    return _map_session_response(db, session, service)


def _map_session_response(
    db: Session,
    session,
    service: SessionsService,
) -> SessionResponse:
    return SessionResponse(
        id=session.id,
        release_id=session.release_id,
        session_group_id=session.session_group_id,
        rating=session.rating,
        mood=session.mood,
        notes=session.notes,
        played_at=session.played_at,
        vinyl_side=session.vinyl_side,
        tracks=_map_session_tracks(service.get_session_tracks(db, session.id)),
        created_at=session.created_at,
        can_edit=service.can_edit_session(session),
        editable_until=service.editable_until(session),
    )


def _map_session_tracks(tracks) -> list[SessionTrackResponse]:
    return [
        SessionTrackResponse(
            position=track.track_position,
            title=track.track_title,
            duration=track.track_duration,
            sequence=track.track_sequence,
        )
        for track in tracks
    ]


def _map_session_group_response(session_group) -> SessionGroupResponse:
    return SessionGroupResponse(
        id=session_group.id,
        title=session_group.title,
        status=session_group.status,
        started_at=session_group.started_at,
        ended_at=session_group.ended_at,
        created_at=session_group.created_at,
        updated_at=session_group.updated_at,
    )
