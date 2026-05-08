from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.identify import IdentifyCandidateResponse, IdentifyResponse
from app.schemas.sessions import ErrorResponse
from app.services.identify_service import DEFAULT_MAX_UPLOAD_SIZE_BYTES, IdentifyService, IdentifyValidationError

router = APIRouter()
UPLOAD_READ_CHUNK_SIZE_BYTES = 1024 * 1024
_identify_service: IdentifyService | None = None


def get_identify_service() -> IdentifyService:
    global _identify_service  # noqa: PLW0603
    if _identify_service is None:
        _identify_service = IdentifyService()
    return _identify_service


@router.post(
    "",
    response_model=IdentifyResponse,
    responses={413: {"model": ErrorResponse}, 415: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
async def identify_release(
    image: Annotated[UploadFile, File(...)],
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[IdentifyService, Depends(get_identify_service)],
):
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
                match_source=candidate.match_source,
                matched_on=list(candidate.matched_on),
                confidence=candidate.confidence,
            )
            for candidate in result.candidates
        ]
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
