"""
ArchScale — Module 1: Communication Ingestion Layer
API router: ingestion endpoints.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Form, HTTPException, UploadFile, status
from fastapi.responses import JSONResponse

from app.models.communication import (
    ErrorResponse,
    IngestionResponse,
    ProjectCommunicationsResponse,
    SourceType,
    TextIngestionRequest,
)
from app.services.ingestion_service import IngestionError, IngestionService
from app.utils.validators import validate_project_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/ingest", tags=["Ingestion"])

# ---------------------------------------------------------------------------
# Shared service instance (can be overridden in tests via app.dependency_overrides)
# ---------------------------------------------------------------------------
_service = IngestionService()


def get_service() -> IngestionService:
    """Return the shared IngestionService instance."""
    return _service


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/text",
    response_model=IngestionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest pasted text or meeting transcript",
    description=(
        "Accepts raw project communication text or a meeting transcript. "
        "source_type must be 'text' or 'transcript'."
    ),
    responses={
        400: {"model": ErrorResponse, "description": "Validation error"},
        422: {"description": "Request body schema error"},
    },
)
async def ingest_text(request: TextIngestionRequest) -> IngestionResponse:
    """POST /api/v1/ingest/text — ingest pasted text or transcript."""
    svc = get_service()
    try:
        record = svc.ingest_text(
            project_id=request.project_id,
            content=request.content,
            source_type=SourceType(request.source_type),
        )
    except IngestionError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected error during text ingestion")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during ingestion.",
        ) from exc

    return IngestionResponse(data=record)


@router.post(
    "/file",
    response_model=IngestionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest a .txt or .pdf file",
    description=(
        "Accepts a multipart file upload (.txt or .pdf). "
        "Extracts plain text from the file, stores the original in storage/raw/, "
        "and persists the normalized record in storage/processed/."
    ),
    responses={
        400: {"model": ErrorResponse, "description": "Validation or extraction error"},
        415: {"model": ErrorResponse, "description": "Unsupported file type"},
    },
)
async def ingest_file(
    project_id: str = Form(..., description="Project this file belongs to."),
    file: UploadFile = ...,
) -> IngestionResponse:
    """POST /api/v1/ingest/file — ingest a .txt or .pdf upload."""
    # Validate project_id early so we get a clean error
    ok, err = validate_project_id(project_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err)

    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file must have a filename.",
        )

    try:
        file_bytes = await file.read()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to read uploaded file: {exc}",
        ) from exc

    svc = get_service()
    try:
        record = svc.ingest_file(
            project_id=project_id,
            filename=file.filename,
            file_bytes=file_bytes,
        )
    except IngestionError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected error during file ingestion")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during file ingestion.",
        ) from exc

    return IngestionResponse(data=record)


@router.get(
    "/project/{project_id}",
    response_model=ProjectCommunicationsResponse,
    summary="List all communications for a project",
    description="Returns all ingested communications for the given project_id, newest first.",
    responses={
        400: {"model": ErrorResponse, "description": "Invalid project_id"},
    },
)
async def list_project_communications(project_id: str) -> ProjectCommunicationsResponse:
    """GET /api/v1/ingest/project/{project_id} — list all records for a project."""
    ok, err = validate_project_id(project_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err)

    svc = get_service()
    records = svc.list_project_communications(project_id)

    return ProjectCommunicationsResponse(
        project_id=project_id,
        count=len(records),
        data=records,
    )


@router.get(
    "/{communication_id}",
    response_model=IngestionResponse,
    summary="Retrieve a communication by ID",
    description="Fetches a previously ingested communication record by its UUID.",
    responses={
        404: {"model": ErrorResponse, "description": "Communication not found"},
    },
)
async def get_communication(communication_id: str) -> IngestionResponse:
    """GET /api/v1/ingest/{communication_id} — retrieve a single record."""
    svc = get_service()
    record = svc.get_communication(communication_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Communication '{communication_id}' not found.",
        )
    return IngestionResponse(data=record)
