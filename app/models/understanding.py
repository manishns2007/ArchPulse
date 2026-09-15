"""
ArchScale — Module 2: Communication Understanding
Pydantic v2 models for the understanding layer output.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Allowed communication type literals
# ---------------------------------------------------------------------------

CommunicationType = Literal[
    "discussion",
    "meeting",
    "instruction",
    "update",
    "approval",
    "request",
    "mixed",
    "unknown",
]

VALID_COMMUNICATION_TYPES: frozenset[str] = frozenset(
    CommunicationType.__args__  # type: ignore[attr-defined]
)


# ---------------------------------------------------------------------------
# Core output model
# ---------------------------------------------------------------------------


class UnderstandingResult(BaseModel):
    """
    Structured understanding of a single communication produced by the LLM.

    This is the canonical output of Module 2 and the input contract for
    Module 3+ (task extraction, decision detection, project memory, etc.).

    Fields intentionally do NOT include formal tasks, deadlines,
    responsibilities, or decisions — those belong to later modules.
    """

    # Traceability — always preserved from the source CommunicationRecord
    project_id: str = Field(
        ...,
        description="Project this communication belongs to.",
        min_length=1,
    )
    communication_id: str = Field(
        ...,
        description="UUID of the source CommunicationRecord from Module 1.",
        min_length=1,
    )

    # LLM-generated understanding fields
    concise_summary: str = Field(
        ...,
        description="Short 1–3 sentence summary of the communication.",
        min_length=1,
    )
    detailed_summary: str = Field(
        ...,
        description="More complete description of what the communication discusses.",
        min_length=1,
    )
    topics: list[str] = Field(
        ...,
        description="Important subjects or themes discussed in the communication.",
    )
    stakeholders: list[str] = Field(
        ...,
        description=(
            "People, teams, roles, or organizations explicitly mentioned "
            "or clearly identifiable from the communication."
        ),
    )
    communication_type: str = Field(
        ...,
        description=(
            "Classified type of communication. "
            "Allowed: discussion, meeting, instruction, update, approval, "
            "request, mixed, unknown."
        ),
    )
    important_context: list[str] = Field(
        ...,
        description=(
            "Important contextual facts that later modules may need to correctly "
            "interpret the communication (e.g. project phase, referenced documents, "
            "dependencies, constraints, background)."
        ),
    )

    # Optional provenance metadata
    analyzed_at: datetime | None = Field(
        default=None,
        description="UTC timestamp of when this understanding was generated.",
    )
    llm_model: str = Field(
        default="",
        description="The LLM model that produced this result.",
    )

    model_config = {"use_enum_values": True}

    @field_validator("communication_type")
    @classmethod
    def communication_type_must_be_valid(cls, v: str) -> str:
        normalized = v.strip().lower()
        if normalized not in VALID_COMMUNICATION_TYPES:
            # Be lenient — fall back to "unknown" rather than raising hard
            return "unknown"
        return normalized

    @field_validator("topics", "stakeholders", "important_context")
    @classmethod
    def list_must_not_contain_blanks(cls, v: list[str]) -> list[str]:
        return [item.strip() for item in v if item.strip()]


# ---------------------------------------------------------------------------
# API request / response schemas
# ---------------------------------------------------------------------------


class AnalyzeRequest(BaseModel):
    """Request body for POST /api/v1/understanding/analyze."""

    communication_id: str = Field(
        ...,
        description="ID of a previously ingested CommunicationRecord to analyze.",
        min_length=1,
    )

    @field_validator("communication_id")
    @classmethod
    def must_not_be_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("communication_id must not be blank.")
        return v.strip()


class UnderstandingResponse(BaseModel):
    """Standard API response wrapper for an understanding result."""

    success: bool = True
    data: UnderstandingResult

    model_config = {"use_enum_values": True}


class UnderstandingErrorResponse(BaseModel):
    """Standard API error response for Module 2."""

    success: bool = False
    error: str
    detail: str | None = None
