import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.analytics import (
    AnalyticsTopRecordItem,
    AnalyticsTopRecordsResponse,
    MonthlyPlayItem,
    MonthlyPlaysResponse,
    MoodDistributionResponse,
    RatingDistributionResponse,
    StyleDistributionResponse,
)
from app.schemas.sessions import ErrorResponse
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
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={"error": {"code": error.code, "message": error.message}},
        )

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
            )
            for item in records
        ]
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
