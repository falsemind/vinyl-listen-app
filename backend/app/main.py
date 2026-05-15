import logging
import math
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response

from app.api.router import api_router
from app.core.config import settings
from app.core.logging import setup_logging
from app.core.rate_limit import (
    RATE_LIMIT_ERROR_CODE,
    RATE_LIMIT_ERROR_MESSAGE,
    ClientKeyResolver,
    InMemoryRateLimiter,
    build_rate_limit_policies,
    resolve_rate_limit_policy,
)
from app.core.runtime_dependencies import log_runtime_dependency_statuses

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # ---- Startup ----
    setup_logging()
    logger.info("Vinyl Listening API starting")
    log_runtime_dependency_statuses()

    yield

    # ---- Shutdown ----
    logger.info("Vinyl Listening API shutting down")


app = FastAPI(title="Vinyl Listening App API", version="0.1.0", lifespan=lifespan)
app.state.rate_limiter = InMemoryRateLimiter()
app.state.client_key_resolver = ClientKeyResolver(
    trust_proxy_headers=settings.inbound_rate_limit_trust_proxy_headers,
)
app.state.rate_limit_policies = build_rate_limit_policies(
    default_limit=settings.inbound_default_rate_limit_per_minute,
    identify_limit=settings.inbound_identify_rate_limit_per_minute,
    window_seconds=settings.inbound_rate_limit_window_seconds,
)


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    if not settings.inbound_rate_limit_enabled:
        return await call_next(request)

    policy = resolve_rate_limit_policy(
        method=request.method,
        path=request.url.path,
        policies=app.state.rate_limit_policies,
    )
    if policy is None:
        return await call_next(request)

    client_key = app.state.client_key_resolver.resolve(request)
    result = app.state.rate_limiter.acquire(client_key=client_key, policy=policy)
    if result.allowed:
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(policy.limit)
        response.headers["X-RateLimit-Remaining"] = str(result.remaining)
        return response

    retry_after_seconds = math.ceil(result.retry_after_seconds)
    return JSONResponse(
        status_code=429,
        content={
            "error": {
                "code": RATE_LIMIT_ERROR_CODE,
                "message": RATE_LIMIT_ERROR_MESSAGE,
            }
        },
        headers={
            "Retry-After": str(retry_after_seconds),
            "X-RateLimit-Limit": str(policy.limit),
            "X-RateLimit-Remaining": "0",
        },
    )


app.include_router(api_router, prefix="/api/v1")


@app.exception_handler(RequestValidationError)
async def request_validation_exception_handler(_request: Request, exc: RequestValidationError):
    request_path = str(_request.url.path)
    errors = exc.errors()
    first_error = errors[0] if errors else {}
    message = first_error.get("msg", "Request validation failed.")

    logger.warning("Request validation failed for %s: %s", request_path, errors)

    return JSONResponse(
        status_code=422,
        content={"error": {"code": "invalid_request", "message": message}},
    )


@app.get("/")
def root():
    return {"status": "vinyl-listen-app backend running"}


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> Response:
    return Response(status_code=204)
