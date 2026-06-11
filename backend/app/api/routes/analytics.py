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

logger = logging.getLogger(__name__)
router = APIRouter()


def get_analytics_service() -> AnalyticsService:
    return AnalyticsService()


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
    month: str = Query(...),
    limit: int = Query(default=10),
    offset: int = Query(default=0),
):
    try:
        page = service.get_sessions_for_month(db, month=month, limit=limit, offset=offset)
    except AnalyticsValidationError as error:
        return _analytics_validation_error_response(error)

    return AnalyticsSessionsResponse(
        sessions=[_map_analytics_session(item) for item in page.sessions],
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


def _map_analytics_session(item: Any) -> AnalyticsSessionItem:
    session = item.session
    release = item.release
    return AnalyticsSessionItem(
        session_id=session.id,
        release_id=release.id,
        session_group_id=session.session_group_id,
        artist=release.artist,
        title=release.title,
        thumbnail_url=release.cover_image_url,
        date=session.played_at.date().isoformat() if session.played_at is not None else None,
        played_at=session.played_at,
        side=session.vinyl_side,
        tracks=[
            SessionTrackResponse(
                position=track.track_position,
                title=track.track_title,
                duration=track.track_duration,
                sequence=track.track_sequence,
            )
            for track in item.tracks
        ],
        rating=session.rating,
        mood=session.mood,
        has_notes=bool(session.notes and session.notes.strip()),
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
