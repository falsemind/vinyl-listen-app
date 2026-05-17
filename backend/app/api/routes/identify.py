from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, File, Request, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database.session import get_db
from app.schemas.identify import IdentifyCandidateResponse, IdentifyJobStatusResponse, IdentifyResponse
from app.schemas.sessions import ErrorResponse
from app.services.identify_job_service import (
    IdentifyCapacityExceededError,
    IdentifyJobExpiredError,
    IdentifyJobNotFoundError,
    IdentifyJobService,
)
from app.services.identify_service import DEFAULT_MAX_UPLOAD_SIZE_BYTES, IdentifyService, IdentifyValidationError

router = APIRouter()
UPLOAD_READ_CHUNK_SIZE_BYTES = 1024 * 1024
_identify_service: IdentifyService | None = None
_identify_job_service: IdentifyJobService | None = None


def get_identify_service() -> IdentifyService:
    global _identify_service  # noqa: PLW0603
    if _identify_service is None:
        _identify_service = IdentifyService()
    return _identify_service


def get_identify_job_service() -> IdentifyJobService:
    global _identify_job_service  # noqa: PLW0603
    if _identify_job_service is None:
        _identify_job_service = IdentifyJobService()
    return _identify_job_service


@router.post(
    "",
    response_model=IdentifyResponse,
    responses={413: {"model": ErrorResponse}, 415: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
async def identify_release(
    image: Annotated[UploadFile, File(...)],
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[IdentifyService, Depends(get_identify_service)],
    job_service: Annotated[IdentifyJobService, Depends(get_identify_job_service)],
):
    _ = request
    try:
        admission_ticket = job_service.acquire_sync_identify_slot()
    except IdentifyCapacityExceededError as error:
        return _capacity_error_response(error)

    try:
        image_bytes = await _read_image_bytes(image)
        result = service.identify(
            db,
            image_bytes=image_bytes,
            filename=image.filename or "",
            content_type=image.content_type or "",
        )
    except IdentifyValidationError as error:
        return JSONResponse(
            status_code=error.status_code,
            content={"error": {"code": error.code, "message": error.message}},
        )
    finally:
        admission_ticket.release()

    return IdentifyResponse(
        candidates=[
            IdentifyCandidateResponse(
                discogs_release_id=candidate.discogs_release_id,
                release_id=candidate.release_id,
                artist=candidate.artist,
                title=candidate.title,
                year=candidate.year,
                label=candidate.label,
                catalog_number=candidate.catalog_number,
                barcode=candidate.barcode,
                cover_image_url=candidate.cover_image_url,
                format=candidate.format,
                match_source=candidate.match_source,
                matched_on=list(candidate.matched_on),
                confidence=candidate.confidence,
            )
            for candidate in result.candidates
        ]
    )


@router.post(
    "/jobs",
    response_model=IdentifyJobStatusResponse,
    status_code=202,
    responses={413: {"model": ErrorResponse}, 415: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
async def create_identify_job(
    image: Annotated[UploadFile, File(...)],
    request: Request,
    background_tasks: BackgroundTasks,
    db: Annotated[Session, Depends(get_db)],
    job_service: Annotated[IdentifyJobService, Depends(get_identify_job_service)],
):
    filename = image.filename or ""
    content_type = image.content_type or ""
    try:
        image_bytes = await _read_image_bytes(image)
        client_key = request.app.state.client_key_resolver.resolve(request)
        job = job_service.create_job(
            db,
            image_bytes=image_bytes,
            filename=filename,
            content_type=content_type,
            client_key=client_key,
        )
    except IdentifyValidationError as error:
        return _error_response(status_code=error.status_code, code=error.code, message=error.message)
    except IdentifyCapacityExceededError as error:
        return _capacity_error_response(error)

    background_tasks.add_task(
        job_service.process_job,
        job.job_id,
        image_bytes=image_bytes,
        filename=filename,
        content_type=content_type,
    )
    return job


@router.get(
    "/jobs/{job_id}",
    response_model=IdentifyJobStatusResponse,
    responses={404: {"model": ErrorResponse}, 410: {"model": ErrorResponse}},
)
def get_identify_job(
    job_id: str,
    db: Annotated[Session, Depends(get_db)],
    job_service: Annotated[IdentifyJobService, Depends(get_identify_job_service)],
):
    try:
        return job_service.get_job(db, job_id)
    except IdentifyJobNotFoundError:
        return _error_response(
            status_code=404,
            code="identify_job_not_found",
            message="Identify job was not found.",
        )
    except IdentifyJobExpiredError:
        return _error_response(
            status_code=410,
            code="identify_job_expired",
            message="Identify job result has expired.",
        )


async def _read_image_bytes(image: UploadFile) -> bytes:
    chunks: list[bytes] = []
    total_size = 0

    while True:
        read_size = min(UPLOAD_READ_CHUNK_SIZE_BYTES, DEFAULT_MAX_UPLOAD_SIZE_BYTES - total_size + 1)
        chunk = await image.read(read_size)
        if not chunk:
            return b"".join(chunks)

        total_size += len(chunk)
        if total_size > DEFAULT_MAX_UPLOAD_SIZE_BYTES:
            raise IdentifyValidationError(
                message=f"Uploaded image exceeds the {DEFAULT_MAX_UPLOAD_SIZE_BYTES} byte limit.",
                status_code=413,
                code="image_too_large",
            )

        chunks.append(chunk)


def _error_response(*, status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message}},
    )


def _capacity_error_response(error: IdentifyCapacityExceededError) -> JSONResponse:
    retry_after_seconds = max(0, settings.identify_capacity_retry_after_seconds)
    return JSONResponse(
        status_code=error.status_code,
        content={"error": {"code": error.code, "message": error.message}},
        headers={"Retry-After": str(retry_after_seconds)},
    )
