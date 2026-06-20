from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.auth_dependencies import AuthenticatedUser, require_authenticated_user
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
    current_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    service: Annotated[DiscogsIntegrationService, Depends(get_discogs_integration_service)],
) -> DiscogsIntegrationStatusResponse:
    return service.get_status(db, user_id=current_user.account.id)


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
    current_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    service: Annotated[DiscogsIntegrationService, Depends(get_discogs_integration_service)],
) -> DiscogsIntegrationStatusResponse | JSONResponse:
    try:
        return service.save_access_token(db, access_token=payload.access_token, user_id=current_user.account.id)
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


@router.delete("/discogs/token", response_model=DiscogsIntegrationStatusResponse)
def delete_discogs_access_token(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    service: Annotated[DiscogsIntegrationService, Depends(get_discogs_integration_service)],
) -> DiscogsIntegrationStatusResponse:
    return service.delete_access_token(db, user_id=current_user.account.id)


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
