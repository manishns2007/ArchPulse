"""
ArchScale — Module 3: Action Extraction
Pydantic v2 models for the action extraction layer.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ---------------------------------------------------------------------------
# Allowed action type literals
# ---------------------------------------------------------------------------

ActionType = Literal[
    "task",
    "request",
    "follow_up",
    "review",
    "deliverable",
    "coordination",
    "other",
]

VALID_ACTION_TYPES: frozenset[str] = frozenset(
    ActionType.__args__  # type: ignore[attr-defined]
)


# ---------------------------------------------------------------------------
# Core extracted action model
# ---------------------------------------------------------------------------


class ExtractedAction(BaseModel):
    """
    A single actionable task/work item identified from project communications.

    Strict negative constraints:
    DO NOT include: owner, responsible_person, deadline, due_date, decision, approval.
    Those belong to Module 4 and later modules.
    """

    model_config = ConfigDict(extra="forbid")

    action_id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Unique identifier for this action (UUID4 generated server-side).",
    )
    action: str = Field(
        ...,
        description="Concise description of the action that needs to happen.",
        min_length=1,
    )
    evidence: str = Field(
        ...,
        description="Exact or minimally sufficient source text supporting the action.",
        min_length=1,
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Numeric confidence score between 0.0 and 1.0.",
    )
    action_type: str = Field(
        default="other",
        description=(
            "Classification of action: task, request, follow_up, review, "
            "deliverable, coordination, other."
        ),
    )

    @field_validator("action_type")
    @classmethod
    def validate_action_type(cls, v: str) -> str:
        normalized = v.strip().lower()
        if normalized not in VALID_ACTION_TYPES:
            return "other"
        return normalized

    @field_validator("action", "evidence")
    @classmethod
    def validate_non_blank(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Field must not be blank.")
        return cleaned


# ---------------------------------------------------------------------------
# Core extraction result model
# ---------------------------------------------------------------------------


class ActionExtractionResult(BaseModel):
    """
    Canonical output of Module 3: Action Extraction.
    Contains all extracted actions with provenance and traceability.
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
    actions: list[ExtractedAction] = Field(
        default_factory=list,
        description="List of extracted actionable items.",
    )
    extracted_at: datetime = Field(
        ...,
        description="Timestamp when the extraction was performed.",
    )
    llm_model: str = Field(
        ...,
        description="The LLM model used to perform the extraction.",
    )


# ---------------------------------------------------------------------------
# API request / response schemas
# ---------------------------------------------------------------------------


class ActionExtractionRequest(BaseModel):
    """Request body for POST /api/v1/actions/extract."""

    communication_id: str = Field(
        ...,
        description="ID of a previously ingested CommunicationRecord to extract actions from.",
        min_length=1,
    )

    @field_validator("communication_id")
    @classmethod
    def must_not_be_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("communication_id must not be blank.")
        return v.strip()


class ActionExtractionResponse(BaseModel):
    """Standard API response wrapper for action extraction."""

    success: bool = True
    data: ActionExtractionResult


class ActionExtractionErrorResponse(BaseModel):
    """Standard API error response for Module 3."""

    success: bool = False
    error: str
    detail: str | None = None
