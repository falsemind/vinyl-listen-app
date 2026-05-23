from typing import Annotated

from fastapi import APIRouter, Depends, status
from starlette.responses import JSONResponse

from app.schemas.ai import AiChatMessage, AiChatRequest, AiChatResponse
from app.schemas.sessions import ErrorResponse
from app.services.ai_insights_service import AiInsightsService, AiInsightsValidationError

router = APIRouter()


def get_ai_insights_service() -> AiInsightsService:
    return AiInsightsService()


@router.post(
    "/chat",
    response_model=AiChatResponse,
    responses={422: {"model": ErrorResponse}},
)
def chat(
    request: AiChatRequest,
    service: Annotated[AiInsightsService, Depends(get_ai_insights_service)],
) -> AiChatResponse | JSONResponse:
    try:
        reply = service.chat(
            message=request.message,
            conversation_id=request.conversation_id,
            client_context=request.client_context.model_dump(exclude_none=True) if request.client_context else None,
        )
    except AiInsightsValidationError as error:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={"error": {"code": error.code, "message": error.message}},
        )

    return AiChatResponse(
        conversation_id=reply.conversation_id,
        message=AiChatMessage(role="assistant", content=reply.content),
        used_tools=reply.used_tools,
    )
