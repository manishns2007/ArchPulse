"""
ArchScale — Module 4: Responsibility Detection
API router: responsibility detection endpoint.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, status

from app.config import settings
from app.llm.provider import FakeLLMProvider, create_provider
from app.models.responsibility import (
    ResponsibilityExtractionErrorResponse,
    ResponsibilityExtractionRequest,
    ResponsibilityExtractionResponse,
)
from app.services.action_extraction_service import (
    ActionExtractionError,
    ActionExtractionProviderError,
    ActionExtractionService,
    ActionExtractionValidationError,
)
from app.services.ingestion_service import IngestionService
from app.services.responsibility_service import (
    ResponsibilityError,
    ResponsibilityProviderError,
    ResponsibilityService,
    ResponsibilityValidationError,
)
from app.services.understanding_service import (
    CommunicationUnderstandingService,
    UnderstandingError,
    UnderstandingProviderError,
    UnderstandingValidationError,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/responsibilities", tags=["Responsibilities"])


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
_responsibility_service = ResponsibilityService(
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


def get_responsibility_service() -> ResponsibilityService:
    """Return the shared ResponsibilityService instance."""
    return _responsibility_service


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/extract",
    response_model=ResponsibilityExtractionResponse,
    status_code=status.HTTP_200_OK,
    summary="Detect responsible parties for extracted actions",
    description=(
        "Takes an ingested `CommunicationRecord` (identified by its `communication_id`), "
        "obtains Module 2 understanding (if `include_understanding_context` is true) and "
        "Module 3 actions (if not supplied directly), and detects who is responsible for "
        "each action.\n\n"
        "Strict boundary: Does NOT extract deadlines, decisions, approvals, or priorities."
    ),
    responses={
        400: {"model": ResponsibilityExtractionErrorResponse, "description": "Invalid input or empty content"},
        404: {"model": ResponsibilityExtractionErrorResponse, "description": "Communication not found"},
        422: {"description": "Validation error in request body"},
        502: {"model": ResponsibilityExtractionErrorResponse, "description": "LLM failure or schema boundary violation"},
    },
)
async def extract_responsibilities(
    request: ResponsibilityExtractionRequest,
) -> ResponsibilityExtractionResponse:
    """POST /api/v1/responsibilities/extract"""
    ingestion_svc = get_ingestion_service()
    understanding_svc = get_understanding_service()
    action_svc = get_action_extraction_service()
    resp_svc = get_responsibility_service()

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

    # Step 2: Obtain Module 2 understanding as contextual grounding if requested
    understanding = None
    if request.include_understanding_context:
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

    # Step 3: Obtain Module 3 actions
    if request.actions is not None:
        actions = request.actions
    else:
        try:
            action_result = action_svc.extract_actions(record, understanding=understanding)
            actions = action_result.actions
        except ActionExtractionError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc
        except (ActionExtractionValidationError, ActionExtractionProviderError) as exc:
            logger.error(
                "Module 3 action extraction failed for communication %s: %s",
                request.communication_id,
                exc,
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Module 3 action extraction failed: {exc}",
            ) from exc
        except Exception as exc:
            logger.exception("Unexpected error obtaining Module 3 actions")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Unexpected error in Module 3 action extraction: {exc}",
            ) from exc

    # Step 4: Perform Responsibility Detection (Module 4)
    try:
        result = resp_svc.detect_responsibilities(
            record=record,
            actions=actions,
            understanding=understanding,
        )
    except ResponsibilityError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except ResponsibilityValidationError as exc:
        logger.error("LLM responsibility detection validation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "The LLM returned a responsibility detection response that violated schema boundaries "
                f"or failed validation: {exc}"
            ),
        ) from exc
    except ResponsibilityProviderError as exc:
        logger.error("LLM provider error during responsibility detection: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The LLM provider is currently unavailable. Please try again later.",
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected error during responsibility detection")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during responsibility detection.",
        ) from exc

    return ResponsibilityExtractionResponse(data=result)


# Alias router for /api/v1/responsibility (singular variant)
alias_router = APIRouter(prefix="/api/v1/responsibility", tags=["Responsibilities"])
alias_router.add_api_route(
    "/extract",
    extract_responsibilities,
    methods=["POST"],
    response_model=ResponsibilityExtractionResponse,
    include_in_schema=False,
)
