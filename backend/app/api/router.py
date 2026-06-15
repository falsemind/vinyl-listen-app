"""Register all API routes in one place."""

from fastapi import APIRouter

from app.api.routes import ai, analytics, collection, health, identify, integrations, releases, sessions

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
    ai.router,
    prefix="/ai",
    tags=["ai"],
)

api_router.include_router(
    analytics.router,
    prefix="/analytics",
    tags=["analytics"],
)

api_router.include_router(
    collection.router,
    prefix="/collection",
    tags=["collection"],
)

api_router.include_router(
    integrations.router,
    prefix="/integrations",
    tags=["integrations"],
)
