import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.router import api_router
from app.core.logging import setup_logging

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ---- Startup ----
    setup_logging()
    logger.info("Vinyl Listening API starting")

    yield

    # ---- Shutdown ----
    logger.info("Vinyl Listening API shutting down")


app = FastAPI(title="Vinyl Listening App API", version="0.1.0", lifespan=lifespan)

app.include_router(api_router)


@app.get("/")
def root():
    return {"status": "vinyl backend running"}
