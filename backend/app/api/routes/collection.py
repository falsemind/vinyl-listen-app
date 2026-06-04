from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.repositories.releases_repository import ReleasesRepository
from app.schemas.collection import (
    CollectionReleaseResponse,
    CollectionReleasesResponse,
    CollectionSyncJobStatusResponse,
)
from app.schemas.sessions import ErrorResponse
from app.services.collection_sync_job_service import (
    CollectionSyncConfigurationError,
    CollectionSyncJobNotFoundError,
    CollectionSyncJobService,
)

router = APIRouter()

_collection_sync_job_service: CollectionSyncJobService | None = None


def get_collection_sync_job_service() -> CollectionSyncJobService:
    global _collection_sync_job_service  # noqa: PLW0603
    if _collection_sync_job_service is None:
        _collection_sync_job_service = CollectionSyncJobService()
    return _collection_sync_job_service


def get_releases_repository() -> ReleasesRepository:
    return ReleasesRepository()


@router.post(
    "/sync",
    response_model=CollectionSyncJobStatusResponse,
    status_code=202,
    responses={500: {"model": ErrorResponse}},
)
def create_collection_sync_job(
    background_tasks: BackgroundTasks,
    db: Annotated[Session, Depends(get_db)],
    job_service: Annotated[CollectionSyncJobService, Depends(get_collection_sync_job_service)],
):
    try:
        job = job_service.create_job(db)
    except CollectionSyncConfigurationError as error:
        return _error_response(status_code=error.status_code, code=error.code, message=error.message)

    background_tasks.add_task(job_service.process_job, job.job_id)
    return job


@router.get(
    "/sync/{job_id}",
    response_model=CollectionSyncJobStatusResponse,
    responses={404: {"model": ErrorResponse}},
)
def get_collection_sync_job(
    job_id: str,
    db: Annotated[Session, Depends(get_db)],
    job_service: Annotated[CollectionSyncJobService, Depends(get_collection_sync_job_service)],
):
    try:
        return job_service.get_job(db, job_id)
    except CollectionSyncJobNotFoundError:
        return _error_response(
            status_code=404,
            code="collection_sync_job_not_found",
            message="Collection sync job was not found.",
        )


@router.get("/releases", response_model=CollectionReleasesResponse)
def list_collection_releases(
    db: Annotated[Session, Depends(get_db)],
    repository: Annotated[ReleasesRepository, Depends(get_releases_repository)],
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
    include_removed: bool = False,
) -> CollectionReleasesResponse:
    releases = repository.list_collection_releases(
        db,
        limit=limit + 1,
        offset=offset,
        include_removed=include_removed,
    )
    visible_releases = releases[:limit]
    return CollectionReleasesResponse(
        items=[_to_collection_release_response(release) for release in visible_releases],
        limit=limit,
        offset=offset,
        has_more=len(releases) > limit,
    )


def _to_collection_release_response(release) -> CollectionReleaseResponse:
    return CollectionReleaseResponse(
        id=release.id,
        discogs_release_id=release.discogs_release_id,
        title=release.title,
        artist=release.artist,
        year=release.year,
        format=release.format,
        label=release.label,
        catalog_number=release.catalog_number,
        styles=release.styles,
        thumb_url=release.thumbnail_url or release.cover_image_url,
        collection_added_at=release.collection_added_at,
        in_collection=release.in_collection,
    )


def _error_response(*, status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"error": {"code": code, "message": message}})
