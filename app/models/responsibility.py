"""
ArchScale — Module 4: Responsibility Detection
Pydantic v2 models for the responsibility detection layer.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.action_extraction import ExtractedAction

# ---------------------------------------------------------------------------
# Allowed responsibility type literals
# ---------------------------------------------------------------------------

ResponsibilityType = Literal[
    "person",
    "role",
    "team",
    "organization",
    "group",
    "unknown",
]

VALID_RESPONSIBILITY_TYPES: frozenset[str] = frozenset(
    ResponsibilityType.__args__  # type: ignore[attr-defined]
)


# ---------------------------------------------------------------------------
# LLM Raw Assignment Payload (Strict validation before server ID generation)
# ---------------------------------------------------------------------------


class ResponsibilityAssignmentPayload(BaseModel):
    """
    Schema for validating raw LLM assignment items.
    Extra fields are strictly forbidden: the LLM must not return responsibility_id,
    owner, deadline, due_date, decision, approval, priority, status, or any other metadata.
    """

    model_config = ConfigDict(extra="forbid")

    action_id: str = Field(
        ...,
        description="Reference to an existing Module 3 action ID.",
        min_length=1,
    )
    responsible_party: str | None = Field(
        default=None,
        description="Name of the person, role, team, org, or group responsible. None if unknown/ambiguous.",
    )
    responsibility_type: ResponsibilityType = Field(
        default="unknown",
        description="Type of responsibility: person, role, team, organization, group, or unknown.",
    )
    evidence: str | None = Field(
        default=None,
        description="Exact source text supporting the responsibility assignment.",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Numeric confidence score between 0.0 and 1.0.",
    )

    @field_validator("responsibility_type", mode="before")
    @classmethod
    def validate_responsibility_type(cls, v: str) -> str:
        if isinstance(v, str):
            normalized = v.strip().lower()
            if normalized in VALID_RESPONSIBILITY_TYPES:
                return normalized
        return "unknown"

    @field_validator("responsible_party", mode="before")
    @classmethod
    def normalize_responsible_party(cls, v: str | None) -> str | None:
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
# Core Responsibility Assignment Model
# ---------------------------------------------------------------------------


class ResponsibilityAssignment(BaseModel):
    """
    A validated responsibility assignment linked to an existing Module 3 action.
    The responsibility_id is generated server-side.
    Extra fields are strictly forbidden.
    """

    model_config = ConfigDict(extra="forbid")

    responsibility_id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Unique identifier for this assignment (UUID4 generated server-side).",
    )
    action_id: str = Field(
        ...,
        description="Reference to the existing Module 3 action ID.",
        min_length=1,
    )
    responsible_party: str | None = Field(
        default=None,
        description="Name of the person, role, team, org, or group responsible. None if unknown/ambiguous.",
    )
    responsibility_type: ResponsibilityType = Field(
        default="unknown",
        description="Type of responsibility classification.",
    )
    evidence: str | None = Field(
        default=None,
        description="Exact source text supporting the responsibility assignment.",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Numeric confidence score between 0.0 and 1.0.",
    )

    @field_validator("responsibility_type", mode="before")
    @classmethod
    def validate_responsibility_type(cls, v: str) -> str:
        if isinstance(v, str):
            normalized = v.strip().lower()
            if normalized in VALID_RESPONSIBILITY_TYPES:
                return normalized
        return "unknown"

    @field_validator("responsible_party", mode="before")
    @classmethod
    def normalize_responsible_party(cls, v: str | None) -> str | None:
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


class ResponsibilityExtractionResult(BaseModel):
    """
    Canonical output of Module 4: Responsibility Detection.
    Contains all responsibility assignments linked to Module 3 actions.
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
    assignments: list[ResponsibilityAssignment] = Field(
        default_factory=list,
        description="List of responsibility assignments linked to Module 3 actions.",
    )
    extracted_at: datetime = Field(
        ...,
        description="Timestamp when responsibility detection was performed.",
    )
    llm_model: str = Field(
        ...,
        description="The LLM model used for detection.",
    )


# ---------------------------------------------------------------------------
# API Request / Response Schemas
# ---------------------------------------------------------------------------


class ResponsibilityExtractionRequest(BaseModel):
    """Request body for POST /api/v1/responsibilities/extract."""

    model_config = ConfigDict(extra="forbid")

    communication_id: str = Field(
        ...,
        description="ID of a previously ingested CommunicationRecord to detect responsibility for.",
        min_length=1,
    )
    include_understanding_context: bool = Field(
        default=True,
        description="Whether to include Module 2 understanding context in LLM prompt.",
    )
    actions: list[ExtractedAction] | None = Field(
        default=None,
        description="Optional list of Module 3 actions. If omitted, actions will be extracted automatically.",
    )

    @field_validator("communication_id")
    @classmethod
    def must_not_be_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("communication_id must not be blank.")
        return v.strip()


class ResponsibilityExtractionResponse(BaseModel):
    """Standard API response wrapper for responsibility extraction."""

    success: bool = True
    data: ResponsibilityExtractionResult


class ResponsibilityExtractionErrorResponse(BaseModel):
    """Standard API error response for Module 4."""

    success: bool = False
    error: str
    detail: str | None = None
