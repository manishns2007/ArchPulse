"""
ArchScale — Module 7: Conversation -> Structured Task
Pydantic v2 models for the structured task composition layer.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.action_extraction import ExtractedAction
from app.models.deadline import DeadlineAssignment
from app.models.decision import ExtractedDecision
from app.models.responsibility import ResponsibilityAssignment

# ---------------------------------------------------------------------------
# Allowed literal types
# ---------------------------------------------------------------------------

TaskStatus = Literal[
    "pending",
    "in_progress",
    "completed",
    "blocked",
    "cancelled",
]

VALID_TASK_STATUSES: frozenset[str] = frozenset(
    TaskStatus.__args__  # type: ignore[attr-defined]
)

TaskPriority = Literal[
    "low",
    "medium",
    "high",
    "urgent",
    "unspecified",
]

VALID_TASK_PRIORITIES: frozenset[str] = frozenset(
    TaskPriority.__args__  # type: ignore[attr-defined]
)


# ---------------------------------------------------------------------------
# Core Structured Task Model
# ---------------------------------------------------------------------------


class StructuredTask(BaseModel):
    """
    Canonical representation of a single structured, traceable task derived from
    already-extracted communication intelligence (Modules 3-6).

    Strict boundary: extra fields are forbidden.
    task_id must always be generated server-side.
    """

    model_config = ConfigDict(extra="forbid")

    task_id: UUID = Field(
        default_factory=uuid4,
        description="Unique identifier for this task (UUID4 generated server-side).",
    )
    project_id: str = Field(
        ...,
        description="Project ID preserved from source CommunicationRecord.",
        min_length=1,
    )
    communication_id: UUID | str = Field(
        ...,
        description="Communication ID preserved from source CommunicationRecord.",
    )
    action_id: UUID | str = Field(
        ...,
        description="Reference to the existing Module 3 action ID.",
    )
    title: str = Field(
        ...,
        description="Concise, actionable, verb-oriented task title.",
        min_length=1,
    )
    description: str = Field(
        ...,
        description="Grounded description of the task.",
        min_length=1,
    )
    responsible_party: str | None = Field(
        default=None,
        description="Who owns/executes this task (from Module 4). None if unassigned.",
    )
    responsibility_type: str | None = Field(
        default=None,
        description="Type of responsibility classification (from Module 4).",
    )
    deadline: str | None = Field(
        default=None,
        description="Temporal expression for when this task is due (from Module 5). None if no deadline.",
    )
    deadline_type: str = Field(
        default="no_deadline",
        description="Deadline type classification (from Module 5).",
    )
    normalized_deadline: str | None = Field(
        default=None,
        description="Normalized ISO date/time if safely determinable (from Module 5).",
    )
    status: TaskStatus = Field(
        default="pending",
        description="Task lifecycle status: pending, in_progress, completed, blocked, cancelled.",
    )
    priority: TaskPriority = Field(
        default="unspecified",
        description="Task priority: low, medium, high, urgent, unspecified.",
    )
    evidence: str = Field(
        ...,
        description="Verbatim source communication text supporting the task.",
        min_length=1,
    )
    decision_context: list[str] = Field(
        default_factory=list,
        description="Relevant decisions or approvals from Module 6 that contextualize this task.",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when this structured task was created server-side.",
    )

    @field_validator("status", mode="before")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if isinstance(v, str):
            normalized = v.strip().lower()
            if normalized in VALID_TASK_STATUSES:
                return normalized
        return "pending"

    @field_validator("priority", mode="before")
    @classmethod
    def validate_priority(cls, v: str) -> str:
        if isinstance(v, str):
            normalized = v.strip().lower()
            if normalized in VALID_TASK_PRIORITIES:
                return normalized
        return "unspecified"

    @field_validator("title", "description", "evidence")
    @classmethod
    def validate_non_blank(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Field must not be blank.")
        return cleaned


# ---------------------------------------------------------------------------
# Core Result Model
# ---------------------------------------------------------------------------


class StructuredTaskResult(BaseModel):
    """
    Canonical output of Module 7: Conversation -> Structured Task.
    """

    model_config = ConfigDict(extra="forbid")

    project_id: str = Field(
        ...,
        description="Project ID preserved from source CommunicationRecord.",
        min_length=1,
    )
    communication_id: UUID | str = Field(
        ...,
        description="Communication ID preserved from source CommunicationRecord.",
    )
    tasks: list[StructuredTask] = Field(
        default_factory=list,
        description="List of structured, traceable tasks.",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when the result was generated server-side.",
    )
    task_count: int = Field(
        default=0,
        description="Count of structured tasks produced.",
    )


# ---------------------------------------------------------------------------
# API Request / Response Schemas
# ---------------------------------------------------------------------------


class StructuredTaskRequest(BaseModel):
    """Request body for POST /api/v1/tasks/structure."""

    model_config = ConfigDict(extra="forbid")

    communication_id: str = Field(
        ...,
        description="ID of a previously ingested CommunicationRecord to structure tasks for.",
        min_length=1,
    )
    include_understanding_context: bool = Field(
        default=True,
        description="Whether to include Module 2 understanding context.",
    )
    actions: list[ExtractedAction] | None = Field(
        default=None,
        description="Optional pre-extracted Module 3 actions. If omitted, will be extracted automatically.",
    )
    responsibilities: list[ResponsibilityAssignment] | None = Field(
        default=None,
        description="Optional pre-extracted Module 4 responsibilities. If omitted, will be extracted automatically.",
    )
    deadlines: list[DeadlineAssignment] | None = Field(
        default=None,
        description="Optional pre-extracted Module 5 deadlines. If omitted, will be extracted automatically.",
    )
    decisions: list[ExtractedDecision] | None = Field(
        default=None,
        description="Optional pre-extracted Module 6 decisions. If omitted, will be extracted automatically.",
    )

    @field_validator("communication_id")
    @classmethod
    def must_not_be_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("communication_id must not be blank.")
        return v.strip()


class StructuredTaskResponse(BaseModel):
    """Standard API response wrapper for structured tasks."""

    success: bool = True
    data: StructuredTaskResult


class StructuredTaskErrorResponse(BaseModel):
    """Standard API error response for Module 7."""

    success: bool = False
    error: str
    detail: str | None = None
