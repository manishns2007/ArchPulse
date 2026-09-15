"""
ArchScale — Module 9: Agentic Project Query & User Interaction
API router: natural language project query endpoint.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse

from app.models.agent import (
    AgentErrorResponse,
    AgentQueryRequest,
    AgentQueryResponse,
)
from app.services.agent_service import AgentService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/agent", tags=["Agent Query"])

# ---------------------------------------------------------------------------
# Shared service instance (overridable in tests)
# ---------------------------------------------------------------------------

_agent_service = AgentService()


def get_agent_service() -> AgentService:
    """Return the shared AgentService instance."""
    return _agent_service


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/query",
    response_model=AgentQueryResponse,
    summary="Natural language project query (Structured POST)",
    description=(
        "Primary agent query interface: receives natural language questions about "
        "tasks, decisions, owners, deadlines, or communication, routes them to M8 memory, "
        "and synthesizes strictly evidence-grounded answers with provenance."
    ),
    responses={
        422: {"model": AgentErrorResponse, "description": "Validation error"},
        500: {"model": AgentErrorResponse, "description": "Server error"},
    },
)
async def agent_query_post(
    request: AgentQueryRequest,
    service: AgentService = Depends(get_agent_service),
) -> JSONResponse:
    """Execute natural language project query."""
    try:
        response = service.query(request)
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "success": True,
                "data": response.model_dump(mode="json"),
            },
        )
    except Exception as exc:
        logger.exception("Unexpected error executing agent query: %s", exc)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"success": False, "error": "internal_error", "detail": str(exc)},
        )


@router.get(
    "/query",
    response_model=AgentQueryResponse,
    summary="Natural language project query (GET query params)",
    description="Convenience GET endpoint for querying project memory.",
    responses={
        422: {"model": AgentErrorResponse, "description": "Validation error"},
        500: {"model": AgentErrorResponse, "description": "Server error"},
    },
)
async def agent_query_get(
    project_id: str = Query(..., min_length=1, description="Owning project ID"),
    query: str = Query(..., min_length=1, description="Natural language question"),
    use_llm: bool = Query(False, description="Whether to use LLM for synthesis"),
    service: AgentService = Depends(get_agent_service),
) -> JSONResponse:
    """Convenience GET endpoint for querying project memory."""
    if not project_id or not project_id.strip():
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"success": False, "error": "validation_error", "detail": "project_id must not be blank."},
        )
    if not query or not query.strip():
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"success": False, "error": "validation_error", "detail": "query must not be blank."},
        )

    req = AgentQueryRequest(
        project_id=project_id.strip(),
        query=query.strip(),
        use_llm=use_llm,
    )
    return await agent_query_post(req, service)
