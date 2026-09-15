"""
ArchScale — Module 1: Communication Ingestion Layer
FastAPI application entry point.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.ingestion import router as ingestion_router
from app.config import settings

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifespan: ensure storage directories exist on startup
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: initialise storage directories."""
    settings.raw_path.mkdir(parents=True, exist_ok=True)
    settings.processed_path.mkdir(parents=True, exist_ok=True)
    logger.info("Storage ready — raw: %s | processed: %s", settings.raw_path, settings.processed_path)
    yield
    logger.info("ArchScale ingestion service shutting down.")


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------


def create_app() -> FastAPI:
    app = FastAPI(
        title="ArchScale — Communication Ingestion API",
        description=(
            "**Module 1** of the ArchScale Project Communication Agent.\n\n"
            "This service accepts raw project communications (pasted text, meeting transcripts, "
            "`.txt` files, and `.pdf` files) and converts them into normalized "
            "`CommunicationRecord` objects for consumption by later modules.\n\n"
            "> ⚠️ No AI extraction is performed in this module."
        ),
        version="1.0.0",
        contact={
            "name": "ArchScale Hackathon Team",
        },
        license_info={
            "name": "MIT",
        },
        lifespan=lifespan,
    )

    # CORS (permissive for development — tighten in production)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routers
    app.include_router(ingestion_router)

    # Health check
    @app.get("/health", tags=["Health"], summary="Health check")
    async def health() -> JSONResponse:
        return JSONResponse({"status": "ok", "module": "ingestion", "version": "1.0.0"})

    return app


app = create_app()
