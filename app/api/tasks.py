"""
ArchScale — Module 7: Conversation -> Structured Task
API router: task structuring endpoint.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, status

from app.config import settings
from app.llm.provider import FakeLLMProvider, create_provider
from app.models.task import (
    StructuredTaskErrorResponse,
    StructuredTaskRequest,
    StructuredTaskResponse,
)
from app.services.action_extraction_service import (
    ActionExtractionError,
    ActionExtractionProviderError,
    ActionExtractionService,
    ActionExtractionValidationError,
)
from app.services.deadline_service import (
    DeadlineError,
    DeadlineProviderError,
    DeadlineService,
    DeadlineValidationError,
)
from app.services.decision_service import (
    DecisionError,
    DecisionProviderError,
    DecisionService,
    DecisionValidationError,
)
from app.services.ingestion_service import IngestionService
from app.services.responsibility_service import (
    ResponsibilityError,
    ResponsibilityProviderError,
    ResponsibilityService,
    ResponsibilityValidationError,
)
from app.services.task_service import (
    TaskError,
    TaskService,
    TaskValidationError,
)
from app.services.understanding_service import (
    CommunicationUnderstandingService,
    UnderstandingError,
    UnderstandingProviderError,
    UnderstandingValidationError,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/tasks", tags=["Tasks"])


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
_deadline_service = DeadlineService(
    llm_provider=create_provider()
    if settings.llm_provider != "fake" and settings.llm_api_key
    else FakeLLMProvider()
)
_decision_service = DecisionService(
    llm_provider=create_provider()
    if settings.llm_provider != "fake" and settings.llm_api_key
    else FakeLLMProvider()
)
_task_service = TaskService()


def get_ingestion_service() -> IngestionService:
    return _ingestion_service


def get_understanding_service() -> CommunicationUnderstandingService:
    return _understanding_service


def get_action_extraction_service() -> ActionExtractionService:
    return _action_extraction_service


def get_responsibility_service() -> ResponsibilityService:
    return _responsibility_service


def get_deadline_service() -> DeadlineService:
    return _deadline_service


def get_decision_service() -> DecisionService:
    return _decision_service


def get_task_service() -> TaskService:
    return _task_service


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/structure",
    response_model=StructuredTaskResponse,
    status_code=status.HTTP_200_OK,
    summary="Compose structured, traceable tasks from communication intelligence",
    description=(
        "Converts already-extracted intelligence from Modules 3-6 (actions, responsibilities, "
        "deadlines, decisions) into a single structured, traceable task representation.\n\n"
        "Strict boundary: Performs deterministic composition; does not re-extract tasks."
    ),
    responses={
        400: {"model": StructuredTaskErrorResponse, "description": "Invalid input or empty content"},
        404: {"model": StructuredTaskErrorResponse, "description": "Communication not found"},
        422: {"description": "Validation error in request body or unknown action ID mapping"},
        502: {"model": StructuredTaskErrorResponse, "description": "Upstream module failure"},
    },
)
async def structure_tasks(
    request: StructuredTaskRequest,
) -> StructuredTaskResponse:
    """POST /api/v1/tasks/structure"""
    ingestion_svc = get_ingestion_service()
    understanding_svc = get_understanding_service()
    action_svc = get_action_extraction_service()
    resp_svc = get_responsibility_service()
    dl_svc = get_deadline_service()
    dec_svc = get_decision_service()
    task_svc = get_task_service()

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
            logger.error("Module 3 action extraction failed for communication %s: %s", request.communication_id, exc)
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

    # Step 4: Obtain Module 4 responsibilities
    if request.responsibilities is not None:
        responsibilities = request.responsibilities
    else:
        try:
            resp_result = resp_svc.detect_responsibilities(record, actions=actions, understanding=understanding)
            responsibilities = resp_result.assignments
        except ResponsibilityError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        except (ResponsibilityValidationError, ResponsibilityProviderError) as exc:
            logger.error("Module 4 responsibility detection failed for communication %s: %s", request.communication_id, exc)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Module 4 responsibility detection failed: {exc}",
            ) from exc
        except Exception as exc:
            logger.exception("Unexpected error obtaining Module 4 responsibilities")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Unexpected error in Module 4 responsibility detection: {exc}",
            ) from exc

    # Step 5: Obtain Module 5 deadlines
    if request.deadlines is not None:
        deadlines = request.deadlines
    else:
        try:
            dl_result = dl_svc.detect_deadlines(
                record=record,
                actions=actions,
                understanding=understanding,
                responsibilities=responsibilities,
            )
            deadlines = dl_result.assignments
        except DeadlineError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        except (DeadlineValidationError, DeadlineProviderError) as exc:
            logger.error("Module 5 deadline detection failed for communication %s: %s", request.communication_id, exc)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Module 5 deadline detection failed: {exc}",
            ) from exc
        except Exception as exc:
            logger.exception("Unexpected error obtaining Module 5 deadlines")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Unexpected error in Module 5 deadline detection: {exc}",
            ) from exc

    # Step 6: Obtain Module 6 decisions
    if request.decisions is not None:
        decisions = request.decisions
    else:
        try:
            dec_result = dec_svc.extract_decisions(record, understanding=understanding)
            decisions = dec_result.decisions
        except DecisionError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        except (DecisionValidationError, DecisionProviderError) as exc:
            logger.error("Module 6 decision extraction failed for communication %s: %s", request.communication_id, exc)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Module 6 decision extraction failed: {exc}",
            ) from exc
        except Exception as exc:
            logger.exception("Unexpected error obtaining Module 6 decisions")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Unexpected error in Module 6 decision extraction: {exc}",
            ) from exc

    # Step 7: Compose Structured Tasks (Module 7)
    try:
        result = task_svc.create_structured_tasks(
            record=record,
            actions=actions,
            responsibilities=responsibilities,
            deadlines=deadlines,
            decisions=decisions,
            understanding=understanding,
        )
    except TaskError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except TaskValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected error during task structuring")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during task structuring.",
        ) from exc

    return StructuredTaskResponse(data=result)
