"""Register all API routes in one place."""

from fastapi import APIRouter, Depends

from app.api.auth_dependencies import require_authenticated_user
from app.api.routes import ai, analytics, auth, collection, health, identify, integrations, releases, sessions

api_router = APIRouter()

api_router.include_router(
    health.router,
    prefix="/health",
    tags=["health"],
)

api_router.include_router(
    auth.router,
    prefix="/auth",
    tags=["auth"],
)

api_router.include_router(
    identify.router,
    prefix="/identify",
    tags=["identify"],
    dependencies=[Depends(require_authenticated_user)],
)

api_router.include_router(
    releases.router,
    prefix="/releases",
    tags=["releases"],
    dependencies=[Depends(require_authenticated_user)],
)

api_router.include_router(
    sessions.router,
    prefix="/sessions",
    tags=["sessions"],
    dependencies=[Depends(require_authenticated_user)],
)

api_router.include_router(
    ai.router,
    prefix="/ai",
    tags=["ai"],
    dependencies=[Depends(require_authenticated_user)],
)

api_router.include_router(
    analytics.router,
    prefix="/analytics",
    tags=["analytics"],
    dependencies=[Depends(require_authenticated_user)],
)

api_router.include_router(
    collection.router,
    prefix="/collection",
    tags=["collection"],
    dependencies=[Depends(require_authenticated_user)],
)

api_router.include_router(
    integrations.router,
    prefix="/integrations",
    tags=["integrations"],
    dependencies=[Depends(require_authenticated_user)],
)
