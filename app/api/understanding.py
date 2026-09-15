"""
ArchScale — Module 2: Communication Understanding
API router: understanding endpoints.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, status

from app.llm.provider import FakeLLMProvider, create_provider
from app.models.understanding import (
    AnalyzeRequest,
    UnderstandingErrorResponse,
    UnderstandingResponse,
)
from app.services.ingestion_service import IngestionService
from app.services.understanding_service import (
    CommunicationUnderstandingService,
    UnderstandingError,
    UnderstandingProviderError,
    UnderstandingValidationError,
)
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/understanding", tags=["Understanding"])


# ---------------------------------------------------------------------------
# Shared service instances
# (overridable in tests exactly the same way as Module 1)
# ---------------------------------------------------------------------------

_ingestion_service = IngestionService()
_understanding_service = CommunicationUnderstandingService(
    llm_provider=create_provider()
    if settings.llm_provider != "fake" and settings.llm_api_key
    else FakeLLMProvider()
)


def get_ingestion_service() -> IngestionService:
    """Return the shared IngestionService instance."""
    return _ingestion_service


def get_understanding_service() -> CommunicationUnderstandingService:
    """Return the shared CommunicationUnderstandingService instance."""
    return _understanding_service


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/analyze",
    response_model=UnderstandingResponse,
    status_code=status.HTTP_200_OK,
    summary="Analyze a communication for understanding",
    description=(
        "Takes an ingested `CommunicationRecord` (identified by its "
        "`communication_id`) and uses an LLM to produce a structured "
        "`UnderstandingResult` containing summary, topics, stakeholders, "
        "communication type, and important context.\n\n"
        "> No task/deadline/responsibility extraction is performed here. "
        "Those belong to Module 3+."
    ),
    responses={
        400: {"model": UnderstandingErrorResponse, "description": "Invalid request or empty content"},
        404: {"model": UnderstandingErrorResponse, "description": "Communication not found"},
        422: {"description": "Request body schema error"},
        502: {"model": UnderstandingErrorResponse, "description": "LLM provider failure"},
    },
)
async def analyze_communication(request: AnalyzeRequest) -> UnderstandingResponse:
    """POST /api/v1/understanding/analyze"""
    ingestion_svc = get_ingestion_service()
    understanding_svc = get_understanding_service()

    # Retrieve the CommunicationRecord from Module 1 storage
    record = ingestion_svc.get_communication(request.communication_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Communication '{request.communication_id}' not found. "
                   "Ingest it first via POST /api/v1/ingest/text or /file.",
        )

    try:
        result = understanding_svc.analyze(record)
    except UnderstandingError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except UnderstandingValidationError as exc:
        logger.error("LLM response validation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The LLM returned a response that could not be validated. "
                   "Please try again.",
        ) from exc
    except UnderstandingProviderError as exc:
        logger.error("LLM provider error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The LLM provider is currently unavailable. Please try again later.",
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected error during understanding analysis")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during analysis.",
        ) from exc

    return UnderstandingResponse(data=result)
