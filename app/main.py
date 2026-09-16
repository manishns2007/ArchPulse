"""
ArchScale — Communication Agent
FastAPI application entry point (Module 1 + Module 2).
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.action_extraction import router as action_extraction_router
from app.api.agent import router as agent_router
from app.api.deadline import router as deadline_router
from app.api.decision import router as decision_router
from app.api.ingestion import router as ingestion_router
from app.api.memory import router as memory_router
from app.api.responsibility import (
    alias_router as responsibility_alias_router,
    router as responsibility_router,
)
from app.api.tasks import router as task_router
from app.api.understanding import (
    alias_router as understanding_alias_router,
    router as understanding_router,
)
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
        title="ArchScale — Project Communication Agent",
        description=(
            "AI-powered Project Communication Agent for the ArchScale Hackathon.\n\n"
            "**Module 1 — Ingestion**: Accepts raw project communications (pasted text, "
            "meeting transcripts, `.txt` and `.pdf` files) and converts them into normalized "
            "`CommunicationRecord` objects.\n\n"
            "**Module 2 — Understanding**: Uses an LLM to produce a structured "
            "`UnderstandingResult` from any ingested communication — summarizing content, "
            "identifying topics, stakeholders, communication type, and important context.\n\n"
            "**Module 3 — Action Extraction**: Identifies actionable work (tasks, requests, "
            "deliverables, reviews, follow-ups, coordination) from project communications.\n\n"
            "**Module 4 — Responsibility Detection**: Detects ownership / responsibility "
            "for extracted actions, linking them to persons, roles, teams, or organizations.\n\n"
            "**Module 5 — Deadline Detection**: Determines when extracted actions are due, "
            "linking them to exact dates, relative days/times, or event-based deadlines.\n\n"
            "**Module 6 — Decision & Approval Extraction**: Identifies confirmed decisions "
            "and explicit approvals made in project communications.\n\n"
            "**Module 7 — Conversation → Structured Task**: Converts already-extracted "
            "intelligence from Modules 3–6 into structured, traceable task items.\n\n"
            "**Module 8 — Project Memory / Searchable Memory**: Indexes upstream communication "
            "intelligence (M1–M7) into persistent, searchable, traceable project memory.\n\n"
            "**Module 9 — Agentic Project Query & User Interaction**: Natural language project "
            "query layer with deterministic routing and evidence-grounded synthesis."
        ),
        version="2.0.0",
        contact={
            "name": "ArchScale Hackathon Team",
        },
        license_info={
            "name": "MIT",
        },
        lifespan=lifespan,
    )

    # CORS: Configurable via CORS_ORIGINS (comma-separated), fallback to ["*"] for development
    cors_origins_raw = os.getenv("CORS_ORIGINS", "*").strip()
    if cors_origins_raw == "*" or not cors_origins_raw:
        cors_origins = ["*"]
        allow_creds = False
    else:
        cors_origins = [orig.strip() for orig in cors_origins_raw.split(",") if orig.strip()]
        allow_creds = True

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=allow_creds,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routers
    app.include_router(ingestion_router)
    app.include_router(understanding_router)
    app.include_router(understanding_alias_router)
    app.include_router(action_extraction_router)
    app.include_router(responsibility_router)
    app.include_router(responsibility_alias_router)
    app.include_router(deadline_router)
    app.include_router(decision_router)
    app.include_router(task_router)
    app.include_router(memory_router)
    app.include_router(agent_router)

    # Health check
    @app.get("/health", tags=["Health"], summary="Health check")
    async def health() -> JSONResponse:
        return JSONResponse({
            "status": "ok",
            "modules": [
                "ingestion",
                "understanding",
                "action_extraction",
                "responsibility",
                "deadline",
                "decision",
                "structured_tasks",
                "project_memory",
                "agent_query",
            ],
            "version": "2.0.0",
        })

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=False)
