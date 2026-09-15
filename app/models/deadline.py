"""
ArchScale — Module 5: Deadline Detection
Pydantic v2 models for the deadline detection layer.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.action_extraction import ExtractedAction
from app.models.responsibility import ResponsibilityAssignment

# ---------------------------------------------------------------------------
# Allowed deadline type literals
# ---------------------------------------------------------------------------

DeadlineType = Literal[
    "exact_date",
    "relative_day",
    "relative_time",
    "event_based",
    "no_deadline",
    "unknown",
]

VALID_DEADLINE_TYPES: frozenset[str] = frozenset(
    DeadlineType.__args__  # type: ignore[attr-defined]
)


# ---------------------------------------------------------------------------
# LLM Raw Assignment Payload (Strict validation before server ID generation)
# ---------------------------------------------------------------------------


class DeadlineAssignmentPayload(BaseModel):
    """
    Schema for validating raw LLM deadline detection items.
    Extra fields are strictly forbidden: the LLM must not return deadline_id,
    owner, responsible_party, decision, approval, priority, status, or any other metadata.
    """

    model_config = ConfigDict(extra="forbid")

    action_id: str = Field(
        ...,
        description="Reference to an existing Module 3 action ID.",
        min_length=1,
    )
    deadline: str | None = Field(
        default=None,
        description="Raw temporal expression specifying when the action is due. None if no deadline.",
    )
    deadline_type: DeadlineType = Field(
        default="no_deadline",
        description="Classification: exact_date, relative_day, relative_time, event_based, no_deadline, unknown.",
    )
    normalized_deadline: str | None = Field(
        default=None,
        description="ISO formatted date/time representation where safely determined; otherwise None.",
    )
    evidence: str | None = Field(
        default=None,
        description="Exact source text supporting the deadline. None if no deadline.",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Numeric confidence score between 0.0 and 1.0.",
    )

    @field_validator("deadline_type", mode="before")
    @classmethod
    def validate_deadline_type(cls, v: str) -> str:
        if isinstance(v, str):
            normalized = v.strip().lower()
            if normalized in VALID_DEADLINE_TYPES:
                return normalized
        return "unknown"

    @field_validator("deadline", mode="before")
    @classmethod
    def normalize_deadline(cls, v: str | None) -> str | None:
        if v is None:
            return None
        cleaned = str(v).strip()
        return cleaned if cleaned else None

    @field_validator("normalized_deadline", mode="before")
    @classmethod
    def normalize_normalized_deadline(cls, v: str | None) -> str | None:
        if v is None:
            return None
        cleaned = str(v).strip()
        return cleaned if cleaned else None

    @field_validator("evidence", mode="before")
    @classmethod
    def normalize_evidence(cls, v: str | None) -> str | None:
        if v is None:
            return None
        cleaned = str(v).strip()
        return cleaned if cleaned else None

    @field_validator("action_id")
    @classmethod
    def validate_action_id_non_blank(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("action_id must not be blank.")
        return cleaned


# ---------------------------------------------------------------------------
# Core Deadline Assignment Model
# ---------------------------------------------------------------------------


class DeadlineAssignment(BaseModel):
    """
    A validated deadline assignment linked to an existing Module 3 action.
    The deadline_id is generated server-side.
    Extra fields are strictly forbidden.
    """

    model_config = ConfigDict(extra="forbid")

    deadline_id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Unique identifier for this assignment (UUID4 generated server-side).",
    )
    action_id: str = Field(
        ...,
        description="Reference to the existing Module 3 action ID.",
        min_length=1,
    )
    deadline: str | None = Field(
        default=None,
        description="Raw temporal expression specifying when the action is due. None if no deadline.",
    )
    deadline_type: DeadlineType = Field(
        default="no_deadline",
        description="Classification: exact_date, relative_day, relative_time, event_based, no_deadline, unknown.",
    )
    normalized_deadline: str | None = Field(
        default=None,
        description="ISO formatted date/time representation where safely determined; otherwise None.",
    )
    evidence: str | None = Field(
        default=None,
        description="Exact source text supporting the deadline. None if no deadline.",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Numeric confidence score between 0.0 and 1.0.",
    )

    @field_validator("deadline_type", mode="before")
    @classmethod
    def validate_deadline_type(cls, v: str) -> str:
        if isinstance(v, str):
            normalized = v.strip().lower()
            if normalized in VALID_DEADLINE_TYPES:
                return normalized
        return "unknown"

    @field_validator("deadline", mode="before")
    @classmethod
    def normalize_deadline(cls, v: str | None) -> str | None:
        if v is None:
            return None
        cleaned = str(v).strip()
        return cleaned if cleaned else None

    @field_validator("normalized_deadline", mode="before")
    @classmethod
    def normalize_normalized_deadline(cls, v: str | None) -> str | None:
        if v is None:
            return None
        cleaned = str(v).strip()
        return cleaned if cleaned else None

    @field_validator("evidence", mode="before")
    @classmethod
    def normalize_evidence(cls, v: str | None) -> str | None:
        if v is None:
            return None
        cleaned = str(v).strip()
        return cleaned if cleaned else None

    @field_validator("action_id")
    @classmethod
    def validate_action_id_non_blank(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("action_id must not be blank.")
        return cleaned


# ---------------------------------------------------------------------------
# Core Extraction Result Model
# ---------------------------------------------------------------------------


class DeadlineExtractionResult(BaseModel):
    """
    Canonical output of Module 5: Deadline Detection.
    Contains all deadline assignments linked deterministically 1-to-1 to Module 3 actions.
    """

    model_config = ConfigDict(extra="forbid")

    project_id: str = Field(
        ...,
        description="Project ID preserved from source CommunicationRecord.",
        min_length=1,
    )
    communication_id: str = Field(
        ...,
        description="Communication ID preserved from source CommunicationRecord.",
        min_length=1,
    )
    assignments: list[DeadlineAssignment] = Field(
        default_factory=list,
        description="List of deadline assignments linked to Module 3 actions.",
    )
    extracted_at: datetime = Field(
        ...,
        description="Timestamp when deadline detection was performed.",
    )
    llm_model: str = Field(
        ...,
        description="The LLM model used for detection.",
    )


# ---------------------------------------------------------------------------
# API Request / Response Schemas
# ---------------------------------------------------------------------------


class DeadlineExtractionRequest(BaseModel):
    """Request body for POST /api/v1/deadlines/extract."""

    model_config = ConfigDict(extra="forbid")

    communication_id: str = Field(
        ...,
        description="ID of a previously ingested CommunicationRecord to detect deadlines for.",
        min_length=1,
    )
    include_context: bool = Field(
        default=True,
        description="Whether to include Module 2 understanding and Module 4 responsibility context.",
    )
    actions: list[ExtractedAction] | None = Field(
        default=None,
        description="Optional pre-extracted Module 3 actions. If omitted, will be obtained automatically.",
    )
    responsibilities: list[ResponsibilityAssignment] | None = Field(
        default=None,
        description="Optional pre-extracted Module 4 responsibilities. If omitted, will be obtained automatically.",
    )

    @field_validator("communication_id")
    @classmethod
    def must_not_be_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("communication_id must not be blank.")
        return v.strip()


class DeadlineExtractionResponse(BaseModel):
    """Standard API response wrapper for deadline detection."""

    success: bool = True
    data: DeadlineExtractionResult


class DeadlineExtractionErrorResponse(BaseModel):
    """Standard API error response for Module 5."""

    success: bool = False
    error: str
    detail: str | None = None
