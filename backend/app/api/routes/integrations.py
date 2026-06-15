from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.integrations import DiscogsIntegrationStatusResponse, DiscogsTokenRequest
from app.schemas.sessions import ErrorResponse
from app.services.discogs_integration_service import (
    DiscogsIntegrationService,
    DiscogsTokenValidationError,
    TokenCipherConfigurationError,
)

router = APIRouter()

_discogs_integration_service: DiscogsIntegrationService | None = None


def get_discogs_integration_service() -> DiscogsIntegrationService:
    global _discogs_integration_service  # noqa: PLW0603
    if _discogs_integration_service is None:
        _discogs_integration_service = DiscogsIntegrationService()
    return _discogs_integration_service


@router.get("/discogs", response_model=DiscogsIntegrationStatusResponse)
def get_discogs_integration_status(
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[DiscogsIntegrationService, Depends(get_discogs_integration_service)],
) -> DiscogsIntegrationStatusResponse:
    return service.get_status(db)


@router.put(
    "/discogs/token",
    response_model=DiscogsIntegrationStatusResponse,
    responses={
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
def save_discogs_access_token(
    payload: DiscogsTokenRequest,
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[DiscogsIntegrationService, Depends(get_discogs_integration_service)],
) -> DiscogsIntegrationStatusResponse | JSONResponse:
    try:
        return service.save_access_token(db, access_token=payload.access_token)
    except DiscogsTokenValidationError as error:
        return _error_response(
            status_code=400,
            code="discogs_token_invalid",
            message=str(error),
        )
    except TokenCipherConfigurationError:
        return _error_response(
            status_code=500,
            code="discogs_token_storage_not_configured",
            message="Discogs token storage is not configured.",
        )


def _error_response(*, status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
            }
        },
    )
