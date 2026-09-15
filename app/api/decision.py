"""
ArchScale — Module 6: Decision & Approval Extraction
API router: decision and approval extraction endpoint.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, status

from app.config import settings
from app.llm.provider import FakeLLMProvider, create_provider
from app.models.decision import (
    DecisionExtractionErrorResponse,
    DecisionExtractionRequest,
    DecisionExtractionResponse,
)
from app.services.decision_service import (
    DecisionError,
    DecisionProviderError,
    DecisionService,
    DecisionValidationError,
)
from app.services.ingestion_service import IngestionService
from app.services.understanding_service import (
    CommunicationUnderstandingService,
    UnderstandingError,
    UnderstandingProviderError,
    UnderstandingValidationError,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/decisions", tags=["Decisions"])


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
_decision_service = DecisionService(
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


def get_decision_service() -> DecisionService:
    """Return the shared DecisionService instance."""
    return _decision_service


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/extract",
    response_model=DecisionExtractionResponse,
    status_code=status.HTTP_200_OK,
    summary="Extract confirmed decisions and approvals from a communication",
    description=(
        "Takes an ingested `CommunicationRecord` (identified by its `communication_id`), "
        "obtains Module 2 understanding (if `include_understanding_context` is true), "
        "and extracts all confirmed decisions and approvals explicitly made.\n\n"
        "Strict boundary: Does NOT extract actions, owners, deadlines, or memory."
    ),
    responses={
        400: {"model": DecisionExtractionErrorResponse, "description": "Invalid input or empty content"},
        404: {"model": DecisionExtractionErrorResponse, "description": "Communication not found"},
        422: {"description": "Validation error in request body"},
        502: {"model": DecisionExtractionErrorResponse, "description": "LLM failure or schema boundary violation"},
    },
)
async def extract_decisions(
    request: DecisionExtractionRequest,
) -> DecisionExtractionResponse:
    """POST /api/v1/decisions/extract"""
    ingestion_svc = get_ingestion_service()
    understanding_svc = get_understanding_service()
    decision_svc = get_decision_service()

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

    # Step 3: Perform Decision Extraction (Module 6)
    try:
        result = decision_svc.extract_decisions(
            record=record,
            understanding=understanding,
        )
    except DecisionError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except DecisionValidationError as exc:
        logger.error("LLM decision extraction validation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "The LLM returned a decision extraction response that violated schema boundaries "
                f"or failed validation: {exc}"
            ),
        ) from exc
    except DecisionProviderError as exc:
        logger.error("LLM provider error during decision extraction: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The LLM provider is currently unavailable. Please try again later.",
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected error during decision extraction")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during decision extraction.",
        ) from exc

    return DecisionExtractionResponse(data=result)
