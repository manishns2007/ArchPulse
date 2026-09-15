"""
ArchScale — Module 8: Project Memory / Searchable Memory
API router: memory indexing, deterministic search, and project overview endpoints.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse

from app.models.memory import (
    MemoryErrorResponse,
    MemoryIndexItemRequest,
    MemoryIndexResponse,
    MemoryItemType,
    MemorySearchRequest,
    MemorySearchResponse,
    ProjectDecisionsResponse,
    ProjectMemoryOverviewResponse,
    ProjectTasksResponse,
    VALID_MEMORY_ITEM_TYPES,
)
from app.services.memory_service import (
    MemoryError,
    MemoryService,
    MemoryValidationError,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/memory", tags=["Project Memory"])

# ---------------------------------------------------------------------------
# Shared service instance (overridable in tests)
# ---------------------------------------------------------------------------

_memory_service = MemoryService()


def get_memory_service() -> MemoryService:
    """Return the shared MemoryService instance."""
    return _memory_service


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/index",
    response_model=MemoryIndexResponse,
    summary="Index an entity into project memory",
    description=(
        "Persists an already-extracted entity (task, decision, approval, communication) "
        "into project memory with strict idempotency and provenance."
    ),
    responses={
        422: {"model": MemoryErrorResponse, "description": "Validation error"},
        400: {"model": MemoryErrorResponse, "description": "Invalid input"},
        500: {"model": MemoryErrorResponse, "description": "Server error"},
    },
)
async def index_item(
    request: MemoryIndexItemRequest,
    service: MemoryService = Depends(get_memory_service),
) -> JSONResponse:
    """Idempotently index a project memory item."""
    try:
        item = service._save_memory_item(
            project_id=request.project_id,
            item_type=request.item_type,
            source_id=request.source_id,
            communication_id=request.communication_id,
            title=request.title,
            content=request.content,
            evidence=request.evidence,
            metadata=request.metadata,
        )
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "success": True,
                "data": {
                    "memory_id": str(item.memory_id),
                    "project_id": item.project_id,
                    "item_type": item.item_type,
                    "source_id": str(item.source_id),
                    "communication_id": str(item.communication_id),
                    "created_at": item.created_at.isoformat(),
                    "updated_at": item.updated_at.isoformat(),
                },
            },
        )
    except MemoryValidationError as exc:
        logger.warning("Memory validation error: %s", exc)
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"success": False, "error": "validation_error", "detail": str(exc)},
        )
    except Exception as exc:
        logger.exception("Unexpected error indexing memory item: %s", exc)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"success": False, "error": "internal_error", "detail": str(exc)},
        )


@router.post(
    "/search",
    response_model=MemorySearchResponse,
    summary="Search project memory (Structured POST)",
    description=(
        "Primary search interface: returns ranked, evidence-backed memory items "
        "using deterministic keyword matching and strict project isolation."
    ),
    responses={
        422: {"model": MemoryErrorResponse, "description": "Validation error"},
        500: {"model": MemoryErrorResponse, "description": "Server error"},
    },
)
async def search_memory_post(
    request: MemorySearchRequest,
    service: MemoryService = Depends(get_memory_service),
) -> JSONResponse:
    """Execute deterministic search across project memory."""
    try:
        result = service.search(request)
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "success": True,
                "data": result.model_dump(mode="json"),
            },
        )
    except MemoryValidationError as exc:
        logger.warning("Search validation error: %s", exc)
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"success": False, "error": "validation_error", "detail": str(exc)},
        )
    except Exception as exc:
        logger.exception("Unexpected error in memory search: %s", exc)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"success": False, "error": "internal_error", "detail": str(exc)},
        )


@router.get(
    "/search",
    response_model=MemorySearchResponse,
    summary="Search project memory (GET query params)",
    description="Convenience GET endpoint for searching project memory via query params.",
    responses={
        422: {"model": MemoryErrorResponse, "description": "Validation error"},
        500: {"model": MemoryErrorResponse, "description": "Server error"},
    },
)
async def search_memory_get(
    project_id: str = Query(..., min_length=1, description="Owning project ID"),
    query: str = Query("", description="Natural query or keyword string"),
    item_type: str | None = Query(None, description="Filter by item_type"),
    responsible_party: str | None = Query(None, description="Filter by owner"),
    status_filter: str | None = Query(None, alias="status", description="Filter by status"),
    deadline: str | None = Query(None, description="Filter by deadline"),
    limit: int = Query(50, ge=1, le=200, description="Max results"),
    service: MemoryService = Depends(get_memory_service),
) -> JSONResponse:
    """Convenience GET search endpoint."""
    if not project_id or not project_id.strip():
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"success": False, "error": "validation_error", "detail": "project_id must not be blank."},
        )

    valid_item_type: MemoryItemType | None = None
    if item_type:
        clean_type = item_type.strip().lower()
        if clean_type not in VALID_MEMORY_ITEM_TYPES:
            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                content={
                    "success": False,
                    "error": "validation_error",
                    "detail": f"item_type must be one of {sorted(VALID_MEMORY_ITEM_TYPES)}",
                },
            )
        valid_item_type = clean_type  # type: ignore[assignment]

    req = MemorySearchRequest(
        project_id=project_id.strip(),
        query=query,
        item_type=valid_item_type,
        responsible_party=responsible_party,
        status=status_filter,
        deadline=deadline,
        limit=limit,
    )
    return await search_memory_post(req, service)


@router.get(
    "/project/{project_id}",
    response_model=ProjectMemoryOverviewResponse,
    summary="Get project memory overview",
    description="Returns aggregate counts of all indexed items for the given project.",
    responses={
        422: {"model": MemoryErrorResponse, "description": "Validation error"},
        500: {"model": MemoryErrorResponse, "description": "Server error"},
    },
)
async def get_project_overview(
    project_id: str,
    service: MemoryService = Depends(get_memory_service),
) -> JSONResponse:
    """Return statistical summary of indexed memory for a project."""
    if not project_id or not project_id.strip():
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"success": False, "error": "validation_error", "detail": "project_id must not be blank."},
        )

    try:
        overview = service.get_project_memory(project_id.strip())
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "success": True,
                "data": overview.model_dump(mode="json"),
            },
        )
    except Exception as exc:
        logger.exception("Unexpected error getting project memory overview: %s", exc)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"success": False, "error": "internal_error", "detail": str(exc)},
        )


@router.get(
    "/project/{project_id}/tasks",
    response_model=ProjectTasksResponse,
    summary="Get project tasks from memory",
    description="Retrieves existing indexed M7 tasks without re-extraction or semantic invention.",
    responses={
        422: {"model": MemoryErrorResponse, "description": "Validation error"},
        500: {"model": MemoryErrorResponse, "description": "Server error"},
    },
)
async def get_project_tasks_endpoint(
    project_id: str,
    status_filter: str | None = Query(None, alias="status", description="Filter by status"),
    responsible_party: str | None = Query(None, description="Filter by responsible party"),
    deadline: str | None = Query(None, description="Filter by deadline"),
    service: MemoryService = Depends(get_memory_service),
) -> JSONResponse:
    """Retrieve indexed structured tasks for a project."""
    if not project_id or not project_id.strip():
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"success": False, "error": "validation_error", "detail": "project_id must not be blank."},
        )

    try:
        tasks_data = service.get_project_tasks(
            project_id=project_id.strip(),
            status=status_filter,
            responsible_party=responsible_party,
            deadline=deadline,
        )
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "success": True,
                "data": tasks_data.model_dump(mode="json"),
            },
        )
    except Exception as exc:
        logger.exception("Unexpected error getting project tasks: %s", exc)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"success": False, "error": "internal_error", "detail": str(exc)},
        )


@router.get(
    "/project/{project_id}/decisions",
    response_model=ProjectDecisionsResponse,
    summary="Get project decisions and approvals from memory",
    description="Retrieves existing indexed M6 decisions/approvals without re-interpretation.",
    responses={
        422: {"model": MemoryErrorResponse, "description": "Validation error"},
        500: {"model": MemoryErrorResponse, "description": "Server error"},
    },
)
async def get_project_decisions_endpoint(
    project_id: str,
    service: MemoryService = Depends(get_memory_service),
) -> JSONResponse:
    """Retrieve indexed decisions and approvals for a project."""
    if not project_id or not project_id.strip():
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"success": False, "error": "validation_error", "detail": "project_id must not be blank."},
        )

    try:
        decisions_data = service.get_project_decisions(project_id.strip())
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "success": True,
                "data": decisions_data.model_dump(mode="json"),
            },
        )
    except Exception as exc:
        logger.exception("Unexpected error getting project decisions: %s", exc)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"success": False, "error": "internal_error", "detail": str(exc)},
        )
