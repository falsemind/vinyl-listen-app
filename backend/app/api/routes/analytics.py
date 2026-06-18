import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.analytics import (
    AnalyticsPagination,
    AnalyticsRecordCountItem,
    AnalyticsRecordCountsResponse,
    AnalyticsSessionItem,
    AnalyticsSessionsResponse,
    AnalyticsTopRecordItem,
    AnalyticsTopRecordsResponse,
    MonthlyPlayItem,
    MonthlyPlaysResponse,
    MoodDistributionResponse,
    RatingDistributionResponse,
    StyleDistributionResponse,
)
from app.schemas.sessions import ErrorResponse, SessionTrackResponse
from app.services.analytics_service import AnalyticsService, AnalyticsValidationError
from app.services.session_groups_service import SessionGroupsService
from app.services.sessions_service import SessionsService
from app.utils.discogs_display import clean_discogs_label_name

logger = logging.getLogger(__name__)
router = APIRouter()


def get_analytics_service() -> AnalyticsService:
    return AnalyticsService()


def get_session_groups_service() -> SessionGroupsService:
    return SessionGroupsService()


def get_sessions_service() -> SessionsService:
    return SessionsService()


@router.get("/plays/monthly", response_model=MonthlyPlaysResponse)
def get_monthly_plays(
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[AnalyticsService, Depends(get_analytics_service)],
):
    plays = service.get_monthly_plays(db)
    return MonthlyPlaysResponse(
        data=[
            MonthlyPlayItem(
                month=item.month,
                plays=item.plays,
            )
            for item in plays
        ]
    )


@router.get(
    "/top-records",
    response_model=AnalyticsTopRecordsResponse,
    responses={422: {"model": ErrorResponse}},
)
def get_top_records(
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[AnalyticsService, Depends(get_analytics_service)],
    limit: int = Query(default=10),
):
    try:
        records = service.get_top_records(db, limit=limit)
    except AnalyticsValidationError as error:
        return _analytics_validation_error_response(error)

    return AnalyticsTopRecordsResponse(
        records=[
            AnalyticsTopRecordItem(
                release_id=item.release.id,
                discogs_release_id=item.release.discogs_release_id,
                artist=item.release.artist,
                title=item.release.title,
                thumbnail_url=item.release.cover_image_url,
                plays=item.plays,
                average_rating=round(item.average_rating, 1) if item.average_rating is not None else None,
                top_track=item.top_track,
                top_mood=item.top_mood,
            )
            for item in records
        ]
    )


@router.get(
    "/sessions",
    response_model=AnalyticsSessionsResponse,
    responses={422: {"model": ErrorResponse}},
)
def get_sessions_for_month(
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[AnalyticsService, Depends(get_analytics_service)],
    session_groups_service: Annotated[SessionGroupsService, Depends(get_session_groups_service)],
    sessions_service: Annotated[SessionsService, Depends(get_sessions_service)],
    month: str = Query(...),
    limit: int = Query(default=10),
    offset: int = Query(default=0),
):
    try:
        page = service.get_sessions_for_month(db, month=month, limit=limit, offset=offset)
    except AnalyticsValidationError as error:
        return _analytics_validation_error_response(error)

    session_group_ids = [
        item.session.session_group_id for item in page.sessions if item.session.session_group_id is not None
    ]
    session_groups_by_id = {
        session_group.id: session_group
        for session_group in session_groups_service.get_session_groups_by_ids(db, session_group_ids)
    }
    tracks_by_session_id = sessions_service.get_tracks_by_session_ids_for_releases(
        db,
        [(item.session.id, item.release) for item in page.sessions],
    )

    return AnalyticsSessionsResponse(
        sessions=[
            _map_analytics_session(
                item,
                tracks=tracks_by_session_id.get(item.session.id, item.tracks),
                session_group=session_groups_by_id.get(item.session.session_group_id),
                session_groups_service=session_groups_service,
            )
            for item in page.sessions
        ],
        pagination=_map_pagination(page.pagination),
    )


@router.get(
    "/records/by-rating",
    response_model=AnalyticsRecordCountsResponse,
    responses={422: {"model": ErrorResponse}},
)
def get_records_for_rating(
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[AnalyticsService, Depends(get_analytics_service)],
    rating: int = Query(...),
    limit: int = Query(default=10),
    offset: int = Query(default=0),
):
    try:
        page = service.get_records_for_rating(db, rating=rating, limit=limit, offset=offset)
    except AnalyticsValidationError as error:
        return _analytics_validation_error_response(error)

    return AnalyticsRecordCountsResponse(
        records=[_map_record_count(item) for item in page.records],
        pagination=_map_pagination(page.pagination),
    )


@router.get(
    "/records/by-mood",
    response_model=AnalyticsRecordCountsResponse,
    responses={422: {"model": ErrorResponse}},
)
def get_records_for_mood(
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[AnalyticsService, Depends(get_analytics_service)],
    mood: str = Query(...),
    limit: int = Query(default=10),
    offset: int = Query(default=0),
):
    try:
        page = service.get_records_for_mood(db, mood=mood, limit=limit, offset=offset)
    except AnalyticsValidationError as error:
        return _analytics_validation_error_response(error)

    return AnalyticsRecordCountsResponse(
        records=[_map_record_count(item) for item in page.records],
        pagination=_map_pagination(page.pagination),
    )


@router.get(
    "/records/by-style",
    response_model=AnalyticsRecordCountsResponse,
    responses={422: {"model": ErrorResponse}},
)
def get_records_for_style(
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[AnalyticsService, Depends(get_analytics_service)],
    style: str = Query(...),
    limit: int = Query(default=10),
    offset: int = Query(default=0),
):
    try:
        page = service.get_records_for_style(db, style=style, limit=limit, offset=offset)
    except AnalyticsValidationError as error:
        return _analytics_validation_error_response(error)

    return AnalyticsRecordCountsResponse(
        records=[_map_record_count(item) for item in page.records],
        pagination=_map_pagination(page.pagination),
    )


@router.get("/rating-distribution", response_model=RatingDistributionResponse)
def get_rating_distribution(
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[AnalyticsService, Depends(get_analytics_service)],
):
    return RatingDistributionResponse(ratings=service.get_rating_distribution(db))


@router.get("/mood-distribution", response_model=MoodDistributionResponse)
def get_mood_distribution(
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[AnalyticsService, Depends(get_analytics_service)],
):
    return MoodDistributionResponse(moods=service.get_mood_distribution(db))


@router.get("/style-distribution", response_model=StyleDistributionResponse)
def get_style_distribution(
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[AnalyticsService, Depends(get_analytics_service)],
):
    return StyleDistributionResponse(styles=service.get_style_distribution(db))


def _analytics_validation_error_response(error: AnalyticsValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={"error": {"code": error.code, "message": error.message}},
    )


def _map_pagination(pagination: Any) -> AnalyticsPagination:
    return AnalyticsPagination(
        limit=pagination.limit,
        offset=pagination.offset,
        total=pagination.total,
        has_more=pagination.has_more,
    )


def _map_analytics_session(
    item: Any,
    *,
    tracks: list[Any] | None = None,
    session_group: Any | None = None,
    session_groups_service: SessionGroupsService | None = None,
) -> AnalyticsSessionItem:
    session = item.session
    release = item.release
    session_tracks = tracks if tracks is not None else item.tracks
    return AnalyticsSessionItem(
        session_id=session.id,
        release_id=release.id,
        session_group_id=session.session_group_id,
        session_group=(
            _map_analytics_session_group(session_group, session_groups_service)
            if session_group is not None and session_groups_service is not None
            else None
        ),
        artist=release.artist,
        title=release.title,
        year=release.year,
        label=clean_discogs_label_name(release.label),
        catalog_number=release.catalog_number,
        thumbnail_url=release.cover_image_url,
        date=session.played_at.date().isoformat() if session.played_at is not None else None,
        played_at=session.played_at,
        side=session.vinyl_side,
        tracks=[
            SessionTrackResponse(
                position=track.track_position,
                artist=track.track_artist,
                title=track.track_title,
                duration=track.track_duration,
                sequence=track.track_sequence,
            )
            for track in session_tracks
        ],
        rating=session.rating,
        mood=session.mood,
        has_notes=bool(session.notes and session.notes.strip()),
    )


def _map_analytics_session_group(session_group: Any, service: SessionGroupsService):
    from app.schemas.sessions import HomeRecentSessionGroupItem

    return HomeRecentSessionGroupItem(
        id=session_group.id,
        title=session_group.title,
        status=session_group.status,
        style_focus=session_group.style_focus,
        mood_direction=session_group.mood_direction,
        session_type=session_group.session_type,
        notes=session_group.notes,
        started_at=session_group.started_at,
        ended_at=session_group.ended_at,
        can_edit=service.can_edit_session_group(session_group),
        editable_until=service.editable_until(session_group),
    )


def _map_record_count(item: Any) -> AnalyticsRecordCountItem:
    release = item.release
    return AnalyticsRecordCountItem(
        release_id=release.id,
        discogs_release_id=release.discogs_release_id,
        artist=release.artist,
        title=release.title,
        thumbnail_url=release.cover_image_url,
        count=item.count,
    )
