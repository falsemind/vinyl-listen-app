from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Response
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database.session import get_db
from app.repositories.collection_folders_repository import CollectionFoldersRepository
from app.repositories.collection_settings_repository import CollectionSettingsRepository
from app.repositories.provider_integration_repository import ProviderIntegrationRepository
from app.repositories.releases_repository import ReleasesRepository
from app.schemas.collection import (
    CollectionFolderResponse,
    CollectionFoldersResponse,
    CollectionReleaseResponse,
    CollectionReleasesResponse,
    CollectionSettingsRequest,
    CollectionSettingsResponse,
    CollectionSourceOfTruth,
    CollectionSyncJobStatusResponse,
)
from app.schemas.releases import ReleaseSearchResponse, ReleaseSearchResult
from app.schemas.sessions import ErrorResponse
from app.services.collection_sync_job_service import (
    CollectionSyncConfigurationError,
    CollectionSyncJobNotFoundError,
    CollectionSyncJobService,
)
from app.utils.discogs_display import clean_discogs_label_name

router = APIRouter()
COLLECTION_ARTIST_QUERY_MAX_LENGTH = 255

_collection_sync_job_service: CollectionSyncJobService | None = None


def get_collection_sync_job_service() -> CollectionSyncJobService:
    global _collection_sync_job_service  # noqa: PLW0603
    if _collection_sync_job_service is None:
        _collection_sync_job_service = CollectionSyncJobService()
    return _collection_sync_job_service


def get_releases_repository() -> ReleasesRepository:
    return ReleasesRepository()


def get_collection_settings_repository() -> CollectionSettingsRepository:
    return CollectionSettingsRepository()


def get_collection_folders_repository() -> CollectionFoldersRepository:
    return CollectionFoldersRepository()


def get_provider_integration_repository() -> ProviderIntegrationRepository:
    return ProviderIntegrationRepository()


@router.get("/settings", response_model=CollectionSettingsResponse)
def get_collection_settings(
    db: Annotated[Session, Depends(get_db)],
    repository: Annotated[CollectionSettingsRepository, Depends(get_collection_settings_repository)],
) -> CollectionSettingsResponse:
    settings_record = repository.get_or_create(db)
    return CollectionSettingsResponse(source_of_truth=settings_record.source_of_truth)


@router.get("/folders", response_model=CollectionFoldersResponse)
def list_collection_folders(
    db: Annotated[Session, Depends(get_db)],
    folder_repository: Annotated[CollectionFoldersRepository, Depends(get_collection_folders_repository)],
    integration_repository: Annotated[ProviderIntegrationRepository, Depends(get_provider_integration_repository)],
) -> CollectionFoldersResponse:
    integration = integration_repository.get_discogs(db)
    if not _has_configured_discogs_collection(integration):
        return CollectionFoldersResponse(discogs_configured=False, folders=[], has_extra_folders=False)

    folders = [
        CollectionFolderResponse(
            id=folder.discogs_folder_id,
            name=folder.name,
            count=folder.item_count,
            is_default=folder.is_default,
        )
        for folder in folder_repository.list_folders(db)
    ]
    return CollectionFoldersResponse(
        discogs_configured=True,
        folders=folders,
        has_extra_folders=any(not folder.is_default for folder in folders),
    )


@router.put("/settings", response_model=CollectionSettingsResponse)
def update_collection_settings(
    payload: CollectionSettingsRequest,
    db: Annotated[Session, Depends(get_db)],
    repository: Annotated[CollectionSettingsRepository, Depends(get_collection_settings_repository)],
    integration_repository: Annotated[ProviderIntegrationRepository, Depends(get_provider_integration_repository)],
) -> CollectionSettingsResponse | JSONResponse:
    if payload.source_of_truth == CollectionSourceOfTruth.DISCOGS:
        integration = integration_repository.get_discogs(db)
        if not _has_configured_discogs_collection(integration):
            return _error_response(
                status_code=400,
                code="discogs_token_required",
                message="Discogs access token is required before using Discogs as source of truth.",
            )

    settings_record = repository.set_source_of_truth(db, payload.source_of_truth)
    return CollectionSettingsResponse(source_of_truth=settings_record.source_of_truth)


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
    "/sync/active",
    response_model=CollectionSyncJobStatusResponse,
    responses={204: {"description": "No active collection sync job"}},
)
def get_active_collection_sync_job(
    db: Annotated[Session, Depends(get_db)],
    job_service: Annotated[CollectionSyncJobService, Depends(get_collection_sync_job_service)],
) -> CollectionSyncJobStatusResponse | Response:
    job = job_service.get_active_job(db)
    if job is None:
        return Response(status_code=204)
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
    limit: Annotated[int, Query(ge=1, le=settings.max_page_limit)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
    artist: Annotated[str | None, Query(min_length=1, max_length=COLLECTION_ARTIST_QUERY_MAX_LENGTH)] = None,
    label: Annotated[str | None, Query(min_length=1, max_length=COLLECTION_ARTIST_QUERY_MAX_LENGTH)] = None,
    favorite: bool = False,
    include_removed: bool = False,
    folder_id: Annotated[int | None, Query(ge=0)] = None,
) -> CollectionReleasesResponse:
    total = repository.count_collection_releases(
        db,
        include_removed=include_removed,
        artist=artist,
        label=label,
        favorite=favorite,
        folder_id=folder_id,
    )
    releases = repository.list_collection_releases(
        db,
        limit=limit + 1,
        offset=offset,
        include_removed=include_removed,
        artist=artist,
        label=label,
        favorite=favorite,
        folder_id=folder_id,
    )
    visible_releases = releases[:limit]
    return CollectionReleasesResponse(
        items=[_to_collection_release_response(release) for release in visible_releases],
        limit=limit,
        offset=offset,
        total=total,
        has_more=offset + len(visible_releases) < total,
        has_favorites=repository.has_favorite_collection_releases(db),
    )


@router.get("/search", response_model=ReleaseSearchResponse)
def search_collection_releases(
    db: Annotated[Session, Depends(get_db)],
    repository: Annotated[ReleasesRepository, Depends(get_releases_repository)],
    artist: Annotated[str | None, Query(min_length=1, max_length=COLLECTION_ARTIST_QUERY_MAX_LENGTH)] = None,
    title: Annotated[str | None, Query(min_length=1)] = None,
    catalog: Annotated[str | None, Query(min_length=1)] = None,
    barcode: Annotated[str | None, Query(min_length=1)] = None,
    year: Annotated[int | None, Query(ge=1900, le=2100)] = None,
    limit: Annotated[int, Query(ge=1, le=settings.max_page_limit)] = 10,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ReleaseSearchResponse:
    releases = repository.search_collection_releases(
        db,
        artist=artist,
        title=title,
        catalog=catalog,
        barcode=barcode,
        year=year,
        limit=limit + 1,
        offset=offset,
    )
    page_releases = releases[:limit]
    return ReleaseSearchResponse(
        results=[
            ReleaseSearchResult(
                release_id=release.id,
                discogs_release_id=release.discogs_release_id,
                artist=release.artist,
                title=release.title,
                year=release.year,
                label=clean_discogs_label_name(release.label),
                catalog_number=release.catalog_number,
                thumbnail_url=release.cover_image_url,
                format=release.format,
            )
            for release in page_releases
        ],
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
        label=clean_discogs_label_name(release.label),
        catalog_number=release.catalog_number,
        styles=release.styles,
        thumb_url=release.thumbnail_url or release.cover_image_url,
        collection_added_at=release.collection_added_at,
        in_collection=release.in_collection,
        is_favorite=release.is_favorite,
    )


def _has_configured_discogs_collection(integration) -> bool:
    return bool(
        integration
        and integration.is_active
        and integration.access_token_ciphertext
        and integration.external_user_id
        and integration.external_username
    )


def _error_response(*, status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"error": {"code": code, "message": message}})
