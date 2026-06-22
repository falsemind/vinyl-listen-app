from typing import Annotated

from fastapi import APIRouter, Depends, UploadFile, status
from fastapi.responses import JSONResponse, Response
from sqlalchemy.orm import Session

from app.api.auth_dependencies import AuthenticatedUser, require_authenticated_user
from app.database.session import get_db
from app.models.releases import ManualRelease, ManualReleaseDraft
from app.schemas.manual_releases import (
    ManualReleaseCoverUploadResponse,
    ManualReleaseDraftListResponse,
    ManualReleaseDraftPayload,
    ManualReleaseDraftResponse,
    ManualReleaseDraftSummaryResponse,
    ManualReleaseSaveRequest,
    ManualReleaseSaveResponse,
)
from app.services.manual_release_policy import (
    MAX_MANUAL_RELEASE_COVER_BYTES,
    MAX_MANUAL_RELEASE_DRAFTS,
    ManualReleaseCoverValidationError,
    ManualReleaseDraftLimitExceeded,
)
from app.services.manual_release_service import (
    ManualReleaseNotFoundError,
    ManualReleaseService,
    ManualReleaseValidationError,
)

router = APIRouter()

_manual_release_service: ManualReleaseService | None = None


def get_manual_release_service() -> ManualReleaseService:
    global _manual_release_service
    if _manual_release_service is None:
        _manual_release_service = ManualReleaseService()
    return _manual_release_service


@router.get("/drafts", response_model=ManualReleaseDraftListResponse)
def list_manual_release_drafts(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    service: Annotated[ManualReleaseService, Depends(get_manual_release_service)],
) -> ManualReleaseDraftListResponse:
    drafts = service.list_drafts(db, user_id=current_user.account.id)
    remaining_slots = max(0, MAX_MANUAL_RELEASE_DRAFTS - len(drafts))
    return ManualReleaseDraftListResponse(
        items=[_draft_summary_response(draft) for draft in drafts],
        remaining_slots=remaining_slots,
    )


@router.get("/drafts/{draft_id}", response_model=ManualReleaseDraftResponse)
def get_manual_release_draft(
    draft_id: str,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    service: Annotated[ManualReleaseService, Depends(get_manual_release_service)],
) -> ManualReleaseDraftResponse | JSONResponse:
    try:
        draft = service.get_draft(db, draft_id, user_id=current_user.account.id)
    except ManualReleaseNotFoundError:
        return _not_found_response()
    return _draft_response(draft)


@router.post("/drafts", response_model=ManualReleaseDraftResponse, status_code=status.HTTP_201_CREATED)
def create_manual_release_draft(
    payload: ManualReleaseDraftPayload,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    service: Annotated[ManualReleaseService, Depends(get_manual_release_service)],
) -> ManualReleaseDraftResponse | JSONResponse:
    try:
        draft = service.create_draft(
            db,
            user_id=current_user.account.id,
            form_data=payload.form_data,
            completion_state=payload.completion_state,
        )
    except ManualReleaseDraftLimitExceeded:
        return _error_response(
            status_code=status.HTTP_409_CONFLICT,
            code="manual_release_draft_limit_reached",
            message="Manual release drafts are limited to 5.",
        )
    return _draft_response(draft)


@router.put("/drafts/{draft_id}", response_model=ManualReleaseDraftResponse)
def update_manual_release_draft(
    draft_id: str,
    payload: ManualReleaseDraftPayload,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    service: Annotated[ManualReleaseService, Depends(get_manual_release_service)],
) -> ManualReleaseDraftResponse | JSONResponse:
    try:
        draft = service.update_draft(
            db,
            draft_id,
            user_id=current_user.account.id,
            form_data=payload.form_data,
            completion_state=payload.completion_state,
        )
    except ManualReleaseNotFoundError:
        return _not_found_response()
    return _draft_response(draft)


@router.delete("/drafts/{draft_id}", response_model=None)
def delete_manual_release_draft(
    draft_id: str,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    service: Annotated[ManualReleaseService, Depends(get_manual_release_service)],
) -> Response | JSONResponse:
    try:
        service.delete_draft(db, draft_id, user_id=current_user.account.id)
    except ManualReleaseNotFoundError:
        return _not_found_response()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("", response_model=ManualReleaseSaveResponse, status_code=status.HTTP_201_CREATED)
def save_manual_release(
    payload: ManualReleaseSaveRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    service: Annotated[ManualReleaseService, Depends(get_manual_release_service)],
) -> ManualReleaseSaveResponse | JSONResponse:
    try:
        release = service.save_release(
            db,
            user_id=current_user.account.id,
            form_data=payload.form_data,
            draft_id=payload.draft_id,
        )
    except ManualReleaseNotFoundError:
        return _not_found_response()
    except ManualReleaseValidationError as error:
        return _error_response(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="manual_release_validation_failed",
            message="Manual release validation failed.",
            field_errors=error.field_errors,
        )
    return _save_response(release)


@router.post("/drafts/{draft_id}/cover", response_model=ManualReleaseCoverUploadResponse)
async def upload_manual_release_draft_cover(
    draft_id: str,
    file: UploadFile,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[AuthenticatedUser, Depends(require_authenticated_user)],
    service: Annotated[ManualReleaseService, Depends(get_manual_release_service)],
) -> ManualReleaseCoverUploadResponse | JSONResponse:
    # Ensure the draft belongs to this user before reading the upload body.
    try:
        service.get_draft(db, draft_id, user_id=current_user.account.id)
    except ManualReleaseNotFoundError:
        return _not_found_response()

    content = await file.read(MAX_MANUAL_RELEASE_COVER_BYTES + 1)
    try:
        result = service.upload_cover(
            db,
            draft_id=draft_id,
            user_id=current_user.account.id,
            content_type=file.content_type,
            image_bytes=content,
        )
    except ManualReleaseCoverValidationError as error:
        status_code = (
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE if "500 KB" in str(error) else status.HTTP_400_BAD_REQUEST
        )
        return _error_response(
            status_code=status_code,
            code="manual_release_cover_invalid",
            message=str(error),
        )
    except ManualReleaseNotFoundError:
        return _not_found_response()
    return ManualReleaseCoverUploadResponse(content_type=result.content_type, size_bytes=result.size_bytes)


def _draft_summary_response(draft: ManualReleaseDraft) -> ManualReleaseDraftSummaryResponse:
    form_data = draft.form_data or {}
    return ManualReleaseDraftSummaryResponse(
        id=draft.id,
        artist=_first_string(form_data.get("artists")),
        title=form_data.get("title"),
        year=form_data.get("year"),
        label=form_data.get("label"),
        catalog_number=form_data.get("catalog_number"),
        format=form_data.get("format"),
        cover_thumbnail_url=draft.cover_thumbnail_url,
        completion_state=draft.completion_state,
        updated_at=draft.updated_at,
    )


def _draft_response(draft: ManualReleaseDraft) -> ManualReleaseDraftResponse:
    summary = _draft_summary_response(draft)
    return ManualReleaseDraftResponse(
        **summary.model_dump(),
        form_data=draft.form_data,
        cover_image_url=draft.cover_image_url,
        cover_content_type=draft.cover_content_type,
        cover_size_bytes=draft.cover_size_bytes,
        created_at=draft.created_at,
    )


def _save_response(release: ManualRelease) -> ManualReleaseSaveResponse:
    return ManualReleaseSaveResponse(
        id=release.id,
        title=release.title,
        artist=release.artist,
        in_collection=release.in_collection,
    )


def _first_string(value: object) -> str | None:
    if isinstance(value, list) and value and isinstance(value[0], str):
        return value[0]
    return None


def _not_found_response() -> JSONResponse:
    return _error_response(
        status_code=status.HTTP_404_NOT_FOUND,
        code="manual_release_draft_not_found",
        message="Manual release draft was not found.",
    )


def _error_response(
    *,
    status_code: int,
    code: str,
    message: str,
    field_errors: dict[str, str] | None = None,
) -> JSONResponse:
    error: dict[str, object] = {"code": code, "message": message}
    if field_errors is not None:
        error["field_errors"] = field_errors
    return JSONResponse(status_code=status_code, content={"error": error})
