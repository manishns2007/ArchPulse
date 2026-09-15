"""
ArchScale — Module 1: Communication Ingestion Layer
Data models for normalized communication records.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator, model_serializer


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class SourceType(str, Enum):
    """Type of source communication."""

    text = "text"
    txt_file = "txt_file"
    pdf_file = "pdf_file"
    transcript = "transcript"


class IngestionStatus(str, Enum):
    """Lifecycle status of an ingested communication."""

    pending = "pending"
    ingested = "ingested"
    failed = "failed"


# ---------------------------------------------------------------------------
# Core record
# ---------------------------------------------------------------------------


class CommunicationRecord(BaseModel):
    """
    Normalized internal representation of a project communication.

    This is the canonical output of the ingestion layer and the contract
    that all later modules (Module 2+) consume.
    """

    project_id: str = Field(
        ...,
        description="Caller-supplied identifier for the owning project.",
        min_length=1,
    )
    communication_id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Auto-generated UUID that uniquely identifies this communication.",
    )
    source_type: SourceType = Field(
        ...,
        description="Origin type of this communication.",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of when this record was ingested.",
    )
    raw_content: str = Field(
        ...,
        description="Plain-text content extracted from the original communication.",
        min_length=1,
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Source-specific metadata (e.g. page_count, filename, char_count).",
    )
    storage_path: str | None = Field(
        default=None,
        description="Relative path to the original raw file in storage/raw/. None for pasted text.",
    )
    status: IngestionStatus = Field(
        default=IngestionStatus.ingested,
        description="Lifecycle status of this ingestion.",
    )

    model_config = {
        "json_encoders": {datetime: lambda v: v.isoformat()},
        "use_enum_values": True,
    }

    @field_validator("project_id")
    @classmethod
    def project_id_must_not_be_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("project_id must not be blank.")
        return v.strip()

    @field_validator("raw_content")
    @classmethod
    def raw_content_must_not_be_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("raw_content must not be empty or whitespace-only.")
        return v.strip()


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class TextIngestionRequest(BaseModel):
    """Request body for POST /api/v1/ingest/text."""

    project_id: str = Field(..., description="Project this communication belongs to.", min_length=1)
    content: str = Field(..., description="Raw communication text to ingest.", min_length=1)
    source_type: SourceType = Field(
        default=SourceType.text,
        description="Must be 'text' or 'transcript'.",
    )

    @field_validator("project_id")
    @classmethod
    def project_id_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("project_id must not be blank.")
        return v.strip()

    @field_validator("content")
    @classmethod
    def content_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("content must not be empty or whitespace-only.")
        return v

    @field_validator("source_type")
    @classmethod
    def source_type_must_be_text_or_transcript(cls, v: SourceType) -> SourceType:
        allowed = {SourceType.text, SourceType.transcript}
        if v not in allowed:
            raise ValueError(
                f"source_type for text ingestion must be one of: "
                f"{[s.value for s in allowed]}."
            )
        return v


class IngestionResponse(BaseModel):
    """Standard API response wrapper for a single ingested communication."""

    success: bool = True
    data: CommunicationRecord

    model_config = {"use_enum_values": True}


class ProjectCommunicationsResponse(BaseModel):
    """Standard API response for listing project communications."""

    success: bool = True
    project_id: str
    count: int
    data: list[CommunicationRecord]

    model_config = {"use_enum_values": True}


class ErrorResponse(BaseModel):
    """Standard API error response."""

    success: bool = False
    error: str
    detail: str | None = None
