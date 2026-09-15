"""
ArchScale — Module 3: Action Extraction
API router: action extraction endpoint.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, status

from app.config import settings
from app.llm.provider import FakeLLMProvider, create_provider
from app.models.action_extraction import (
    ActionExtractionErrorResponse,
    ActionExtractionRequest,
    ActionExtractionResponse,
)
from app.services.action_extraction_service import (
    ActionExtractionError,
    ActionExtractionProviderError,
    ActionExtractionService,
    ActionExtractionValidationError,
)
from app.services.ingestion_service import IngestionService
from app.services.understanding_service import (
    CommunicationUnderstandingService,
    UnderstandingError,
    UnderstandingProviderError,
    UnderstandingValidationError,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/actions", tags=["Actions"])


# ---------------------------------------------------------------------------
# Shared service instances
# (overridable in tests)
# ---------------------------------------------------------------------------

_ingestion_service = IngestionService()
_understanding_service = CommunicationUnderstandingService(
    llm_provider=create_provider()
    if settings.llm_provider != "fake" and settings.llm_api_key
    else FakeLLMProvider()
)
_action_extraction_service = ActionExtractionService(
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


def get_action_extraction_service() -> ActionExtractionService:
    """Return the shared ActionExtractionService instance."""
    return _action_extraction_service


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/extract",
    response_model=ActionExtractionResponse,
    status_code=status.HTTP_200_OK,
    summary="Extract actionable work items from a communication",
    description=(
        "Takes an ingested `CommunicationRecord` (identified by its `communication_id`), "
        "obtains Module 2 `UnderstandingResult` for contextual grounding (with controlled "
        "error handling if Module 2 fails), and uses an LLM to identify all actionable tasks, "
        "requests, deliverables, reviews, follow-ups, and coordination items.\n\n"
        "Strict boundary: Does NOT assign owners, deadlines, decisions, or memory."
    ),
    responses={
        400: {"model": ActionExtractionErrorResponse, "description": "Invalid input or empty content"},
        404: {"model": ActionExtractionErrorResponse, "description": "Communication not found"},
        422: {"description": "Validation error in request body"},
        502: {"model": ActionExtractionErrorResponse, "description": "LLM provider failure or unparseable response"},
    },
)
async def extract_actions(request: ActionExtractionRequest) -> ActionExtractionResponse:
    """POST /api/v1/actions/extract"""
    ingestion_svc = get_ingestion_service()
    understanding_svc = get_understanding_service()
    action_svc = get_action_extraction_service()

    # Step 1: Retrieve source CommunicationRecord from Module 1
    record = ingestion_svc.get_communication(request.communication_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Communication '{request.communication_id}' not found. "
                "Ingest it first via POST /api/v1/ingest/text or /file."
            ),
        )

    # Step 2: Obtain Module 2 understanding as contextual grounding.
    # Controlled error: do not silently fall back to raw content if Module 2 fails.
    try:
        understanding = understanding_svc.analyze(record)
    except (UnderstandingError, UnderstandingValidationError, UnderstandingProviderError) as exc:
        logger.error(
            "Module 2 understanding failed for communication %s: %s",
            request.communication_id,
            exc,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Module 2 understanding could not be generated: {exc}",
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected error obtaining Module 2 understanding")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error in Module 2 understanding: {exc}",
        ) from exc

    # Step 3: Perform Action Extraction (Module 3)
    try:
        result = action_svc.extract_actions(record, understanding=understanding)
    except ActionExtractionError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except ActionExtractionValidationError as exc:
        logger.error("LLM action extraction response validation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The LLM returned an action extraction response that could not be validated. Please try again.",
        ) from exc
    except ActionExtractionProviderError as exc:
        logger.error("LLM provider error during action extraction: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The LLM provider is currently unavailable. Please try again later.",
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected error during action extraction")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during action extraction.",
        ) from exc

    return ActionExtractionResponse(data=result)
