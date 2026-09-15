"""
ArchScale — Module 6: Decision & Approval Extraction
Pydantic v2 models for the decision and approval extraction layer.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

# ---------------------------------------------------------------------------
# Allowed literal types
# ---------------------------------------------------------------------------

DecisionItemType = Literal["decision", "approval"]

VALID_ITEM_TYPES: frozenset[str] = frozenset(
    DecisionItemType.__args__  # type: ignore[attr-defined]
)

DecisionStatus = Literal["decided", "approved", "rejected"]

VALID_STATUSES: frozenset[str] = frozenset(
    DecisionStatus.__args__  # type: ignore[attr-defined]
)


# ---------------------------------------------------------------------------
# LLM Raw Item Payload (Strict validation before server ID generation)
# ---------------------------------------------------------------------------


class ExtractedDecisionPayload(BaseModel):
    """
    Schema for validating raw LLM decision/approval items.
    Extra fields are strictly forbidden: the LLM must not return decision_id,
    owner, responsible_party, deadline, due_date, priority, task, status, or any other metadata.
    """

    model_config = ConfigDict(extra="forbid")

    item_type: DecisionItemType = Field(
        ...,
        description="Classification: 'decision' (choice/conclusion/agreed course) or 'approval' (authorized/accepted).",
    )
    description: str = Field(
        ...,
        description="Concise description of what was explicitly decided or approved.",
        min_length=1,
    )
    subject: str | None = Field(
        default=None,
        description="Optional subject/topic of the decision or approval (e.g. 'kitchen counter', 'staircase design').",
    )
    status: DecisionStatus = Field(
        default="decided",
        description="Status: 'decided', 'approved', or 'rejected'.",
    )
    evidence: str = Field(
        ...,
        description="Exact source text quote supporting the decision or approval.",
        min_length=1,
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Numeric confidence score between 0.0 and 1.0.",
    )

    @field_validator("item_type", mode="before")
    @classmethod
    def validate_item_type(cls, v: str) -> str:
        if isinstance(v, str):
            normalized = v.strip().lower()
            if normalized in VALID_ITEM_TYPES:
                return normalized
        raise ValueError(f"item_type must be one of {sorted(VALID_ITEM_TYPES)}")

    @field_validator("status", mode="before")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if isinstance(v, str):
            normalized = v.strip().lower()
            if normalized in VALID_STATUSES:
                return normalized
        return "decided"

    @field_validator("description", "evidence")
    @classmethod
    def validate_non_blank(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Field must not be blank.")
        return cleaned

    @field_validator("subject", mode="before")
    @classmethod
    def normalize_subject(cls, v: str | None) -> str | None:
        if v is None:
            return None
        cleaned = str(v).strip()
        return cleaned if cleaned else None


# ---------------------------------------------------------------------------
# Core Extracted Decision Model
# ---------------------------------------------------------------------------


class ExtractedDecision(BaseModel):
    """
    A validated decision or approval item extracted from a communication.
    The decision_id is generated server-side.
    Extra fields are strictly forbidden.
    """

    model_config = ConfigDict(extra="forbid")

    decision_id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Unique identifier for this decision/approval (UUID4 generated server-side).",
    )
    item_type: DecisionItemType = Field(
        ...,
        description="Classification: 'decision' or 'approval'.",
    )
    description: str = Field(
        ...,
        description="Concise description of what was decided or approved.",
        min_length=1,
    )
    subject: str | None = Field(
        default=None,
        description="Optional subject/topic of the decision or approval.",
    )
    status: DecisionStatus = Field(
        default="decided",
        description="Status: 'decided', 'approved', or 'rejected'.",
    )
    evidence: str = Field(
        ...,
        description="Exact source text quote supporting the decision or approval.",
        min_length=1,
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Numeric confidence score between 0.0 and 1.0.",
    )

    @field_validator("item_type", mode="before")
    @classmethod
    def validate_item_type(cls, v: str) -> str:
        if isinstance(v, str):
            normalized = v.strip().lower()
            if normalized in VALID_ITEM_TYPES:
                return normalized
        raise ValueError(f"item_type must be one of {sorted(VALID_ITEM_TYPES)}")

    @field_validator("status", mode="before")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if isinstance(v, str):
            normalized = v.strip().lower()
            if normalized in VALID_STATUSES:
                return normalized
        return "decided"

    @field_validator("description", "evidence")
    @classmethod
    def validate_non_blank(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Field must not be blank.")
        return cleaned

    @field_validator("subject", mode="before")
    @classmethod
    def normalize_subject(cls, v: str | None) -> str | None:
        if v is None:
            return None
        cleaned = str(v).strip()
        return cleaned if cleaned else None


# ---------------------------------------------------------------------------
# Core Extraction Result Model
# ---------------------------------------------------------------------------


class DecisionExtractionResult(BaseModel):
    """
    Canonical output of Module 6: Decision & Approval Extraction.
    Contains all decisions and approvals extracted from a communication.
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
    decisions: list[ExtractedDecision] = Field(
        default_factory=list,
        description="List of extracted decisions and approvals.",
    )
    extracted_at: datetime = Field(
        ...,
        description="Timestamp when extraction was performed.",
    )
    llm_model: str = Field(
        ...,
        description="The LLM model used for extraction.",
    )


# ---------------------------------------------------------------------------
# API Request / Response Schemas
# ---------------------------------------------------------------------------


class DecisionExtractionRequest(BaseModel):
    """Request body for POST /api/v1/decisions/extract."""

    model_config = ConfigDict(extra="forbid")

    communication_id: str = Field(
        ...,
        description="ID of a previously ingested CommunicationRecord to extract decisions from.",
        min_length=1,
    )
    include_understanding_context: bool = Field(
        default=True,
        description="Whether to include Module 2 understanding context in LLM prompt.",
    )

    @field_validator("communication_id")
    @classmethod
    def must_not_be_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("communication_id must not be blank.")
        return v.strip()


class DecisionExtractionResponse(BaseModel):
    """Standard API response wrapper for decision extraction."""

    success: bool = True
    data: DecisionExtractionResult


class DecisionExtractionErrorResponse(BaseModel):
    """Standard API error response for Module 6."""

    success: bool = False
    error: str
    detail: str | None = None
