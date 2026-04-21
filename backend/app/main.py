import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.core.logging import setup_logging

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # ---- Startup ----
    setup_logging()
    logger.info("Vinyl Listening API starting")

    yield

    # ---- Shutdown ----
    logger.info("Vinyl Listening API shutting down")


app = FastAPI(title="Vinyl Listening App API", version="0.1.0", lifespan=lifespan)

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
