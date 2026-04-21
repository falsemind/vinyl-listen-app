"""Register all API routes in one place."""

from fastapi import APIRouter

from app.api.routes import analytics, health, identify, releases, sessions

api_router = APIRouter()

api_router.include_router(
    health.router,
    prefix="/health",
    tags=["health"],
)

api_router.include_router(
    identify.router,
    prefix="/identify",
    tags=["identify"],
)

api_router.include_router(
    releases.router,
    prefix="/releases",
    tags=["releases"],
)

api_router.include_router(
    sessions.router,
    prefix="/sessions",
    tags=["sessions"],
)

api_router.include_router(
    analytics.router,
    prefix="/analytics",
    tags=["analytics"],
)
