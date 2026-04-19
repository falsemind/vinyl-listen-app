import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.releases import ReleaseImportRequest, ReleaseImportResponse, ReleaseResponse
from app.services.discogs_service import DiscogsClientError
from app.services.release_import_service import ReleaseImportService

logger = logging.getLogger(__name__)
router = APIRouter()


def get_release_import_service() -> ReleaseImportService:
    return ReleaseImportService()


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
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from error
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
