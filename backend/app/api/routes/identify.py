from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.identify import IdentifyCandidateResponse, IdentifyResponse
from app.schemas.sessions import ErrorResponse
from app.services.identify_service import IdentifyService, IdentifyValidationError

router = APIRouter()


def get_identify_service() -> IdentifyService:
    return IdentifyService()


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
        result = service.identify(
            db,
            image_bytes=await image.read(),
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
