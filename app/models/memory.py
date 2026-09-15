"""
ArchScale — Module 8: Project Memory / Searchable Memory
Pydantic v2 models for the project memory indexing and retrieval layer.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.task import StructuredTask

# ---------------------------------------------------------------------------
# Allowed literal types
# ---------------------------------------------------------------------------

MemoryItemType = Literal[
    "communication",
    "task",
    "decision",
    "approval",
    "action",
]

VALID_MEMORY_ITEM_TYPES: frozenset[str] = frozenset(
    MemoryItemType.__args__  # type: ignore[attr-defined]
)


# ---------------------------------------------------------------------------
# Core Project Memory Item Model
# ---------------------------------------------------------------------------


class ProjectMemoryItem(BaseModel):
    """
    Canonical representation of an indexed project memory item.
    Derived from upstream outputs (M1-M7) with strict traceability.

    Strict boundary: extra fields are forbidden.
    memory_id must always be generated server-side using UUID4.
    """

    model_config = ConfigDict(extra="forbid")

    memory_id: UUID = Field(
        default_factory=uuid4,
        description="Unique identifier for this memory item (UUID4 generated server-side).",
    )
    project_id: str = Field(
        ...,
        description="Caller-supplied identifier for the owning project.",
        min_length=1,
    )
    item_type: MemoryItemType = Field(
        ...,
        description="Classification of the memory item: communication, task, decision, approval, action.",
    )
    source_id: UUID | str = Field(
        ...,
        description="Authoritative ID of the source entity in upstream module (e.g. task_id, decision_id, communication_id).",
    )
    communication_id: UUID | str = Field(
        ...,
        description="Traceability link to the original CommunicationRecord.",
    )
    title: str = Field(
        ...,
        description="Concise, searchable title for the memory item.",
        min_length=1,
    )
    content: str = Field(
        ...,
        description="Searchable content/description of the memory item.",
        min_length=1,
    )
    evidence: str | None = Field(
        default=None,
        description="Exact source quotation providing evidence for this memory item.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Structured attributes preserved from upstream modules (e.g. owner, deadline, status).",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when this memory item was created server-side.",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when this memory item was last updated server-side.",
    )

    @field_validator("item_type", mode="before")
    @classmethod
    def validate_item_type(cls, v: str) -> str:
        if isinstance(v, str):
            normalized = v.strip().lower()
            if normalized in VALID_MEMORY_ITEM_TYPES:
                return normalized
        raise ValueError(f"item_type must be one of {sorted(VALID_MEMORY_ITEM_TYPES)}")

    @field_validator("project_id", "title", "content")
    @classmethod
    def validate_non_blank(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Field must not be blank.")
        return cleaned


# ---------------------------------------------------------------------------
# Search Models
# ---------------------------------------------------------------------------


class MemorySearchRequest(BaseModel):
    """
    Search request for retrieving project memory items.
    Strict boundary: extra fields are forbidden.
    """

    model_config = ConfigDict(extra="forbid")

    project_id: str = Field(
        ...,
        description="Project ID to search within (project isolation enforced).",
        min_length=1,
    )
    query: str = Field(
        default="",
        description="Natural language question or keyword query to search.",
    )
    item_type: MemoryItemType | None = Field(
        default=None,
        description="Optional filter by item type (communication, task, decision, approval, action).",
    )
    responsible_party: str | None = Field(
        default=None,
        description="Optional filter by responsible party / owner (for tasks).",
    )
    status: str | None = Field(
        default=None,
        description="Optional filter by status (e.g. pending, completed, decided, approved).",
    )
    deadline: str | None = Field(
        default=None,
        description="Optional filter by deadline temporal expression.",
    )
    limit: int = Field(
        default=50,
        ge=1,
        le=200,
        description="Maximum number of search results to return.",
    )

    @field_validator("project_id")
    @classmethod
    def validate_project_id_non_blank(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("project_id must not be blank.")
        return cleaned


class MemorySearchResultItem(BaseModel):
    """
    An individual search result with relevance score and provenance.
    Strict boundary: extra fields are forbidden.
    """

    model_config = ConfigDict(extra="forbid")

    memory_id: UUID | str = Field(
        ...,
        description="Unique identifier of the memory item.",
    )
    project_id: str = Field(
        ...,
        description="Owning project ID.",
    )
    item_type: MemoryItemType = Field(
        ...,
        description="Classification of the memory item.",
    )
    source_id: UUID | str = Field(
        ...,
        description="Authoritative upstream source entity ID.",
    )
    communication_id: UUID | str = Field(
        ...,
        description="Original communication ID for complete traceability.",
    )
    title: str = Field(
        ...,
        description="Title of the memory item.",
    )
    content: str = Field(
        ...,
        description="Content of the memory item.",
    )
    evidence: str | None = Field(
        default=None,
        description="Grounded verbatim evidence quote.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Associated structured metadata.",
    )
    score: float = Field(
        default=0.0,
        description="Deterministic relevance score.",
    )
    retrieval_mode: str = Field(
        default="keyword",
        description="Mode used for retrieval ('keyword').",
    )


class MemorySearchResult(BaseModel):
    """
    Search output payload containing matching memory items.
    Strict boundary: extra fields are forbidden.
    """

    model_config = ConfigDict(extra="forbid")

    project_id: str = Field(
        ...,
        description="Project ID searched.",
    )
    query: str = Field(
        ...,
        description="Query searched.",
    )
    results: list[MemorySearchResultItem] = Field(
        default_factory=list,
        description="Ranked list of matching memory items.",
    )
    result_count: int = Field(
        default=0,
        description="Number of results returned.",
    )
    retrieval_mode: str = Field(
        default="keyword",
        description="Retrieval mode used (keyword).",
    )


class MemorySearchResponse(BaseModel):
    """Standard API response wrapper for memory search."""

    model_config = ConfigDict(extra="forbid")

    success: bool = True
    data: MemorySearchResult


# ---------------------------------------------------------------------------
# Project Overview Models
# ---------------------------------------------------------------------------


class ProjectMemoryOverview(BaseModel):
    """Structured statistical overview of indexed project memory."""

    model_config = ConfigDict(extra="forbid")

    project_id: str = Field(
        ...,
        description="Owning project ID.",
    )
    communications: int = Field(
        default=0,
        description="Count of indexed communication records.",
    )
    tasks: int = Field(
        default=0,
        description="Count of indexed structured tasks.",
    )
    decisions: int = Field(
        default=0,
        description="Count of indexed decisions.",
    )
    approvals: int = Field(
        default=0,
        description="Count of indexed approvals.",
    )
    memory_items: int = Field(
        default=0,
        description="Total count of all memory items.",
    )


class ProjectMemoryOverviewResponse(BaseModel):
    """Standard API response wrapper for project overview."""

    model_config = ConfigDict(extra="forbid")

    success: bool = True
    data: ProjectMemoryOverview


# ---------------------------------------------------------------------------
# Task & Decision Retrieval Models
# ---------------------------------------------------------------------------


class ProjectTasksData(BaseModel):
    """Container for project tasks retrieval."""

    model_config = ConfigDict(extra="forbid")

    project_id: str
    tasks: list[StructuredTask]
    task_count: int


class ProjectTasksResponse(BaseModel):
    """Standard API response wrapper for task-focused retrieval."""

    model_config = ConfigDict(extra="forbid")

    success: bool = True
    data: ProjectTasksData


class DecisionItemData(BaseModel):
    """Individual decision item in project decisions response."""

    model_config = ConfigDict(extra="forbid")

    decision_id: str
    item_type: str
    description: str
    subject: str | None = None
    status: str
    evidence: str
    communication_id: str


class ProjectDecisionsData(BaseModel):
    """Container for project decisions retrieval."""

    model_config = ConfigDict(extra="forbid")

    project_id: str
    decisions: list[DecisionItemData]
    decision_count: int


class ProjectDecisionsResponse(BaseModel):
    """Standard API response wrapper for decision-focused retrieval."""

    model_config = ConfigDict(extra="forbid")

    success: bool = True
    data: ProjectDecisionsData


# ---------------------------------------------------------------------------
# Memory Indexing Request / Response
# ---------------------------------------------------------------------------


class MemoryIndexItemRequest(BaseModel):
    """Request payload for indexing an individual memory item."""

    model_config = ConfigDict(extra="forbid")

    project_id: str = Field(..., min_length=1)
    item_type: MemoryItemType
    source_id: str = Field(..., min_length=1)
    communication_id: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    content: str = Field(..., min_length=1)
    evidence: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class MemoryIndexResponse(BaseModel):
    """Standard API response wrapper for memory indexing."""

    model_config = ConfigDict(extra="forbid")

    success: bool = True
    data: dict[str, Any]


class MemoryErrorResponse(BaseModel):
    """Standard API error response for Module 8."""

    model_config = ConfigDict(extra="forbid")

    success: bool = False
    error: str
    detail: str | None = None
