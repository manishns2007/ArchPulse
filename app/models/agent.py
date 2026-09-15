"""
ArchScale — Module 9: Agentic Project Query & User Interaction
Pydantic v2 data models for query understanding, routing, and evidence-grounded responses.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

# ---------------------------------------------------------------------------
# Allowed Query Intent Types
# ---------------------------------------------------------------------------

QueryIntent = Literal[
    "task",
    "responsibility",
    "deadline",
    "decision",
    "approval",
    "communication",
    "project_overview",
    "general_memory",
]

VALID_QUERY_INTENTS: frozenset[str] = frozenset(
    QueryIntent.__args__  # type: ignore[attr-defined]
)


# ---------------------------------------------------------------------------
# Core Agent Models
# ---------------------------------------------------------------------------


class AgentQueryRequest(BaseModel):
    """
    Request model for natural language project query.
    Strict schema: extra fields are forbidden.
    """

    model_config = ConfigDict(extra="forbid")

    project_id: str = Field(
        ...,
        description="Project ID to query (strict project isolation enforced).",
        min_length=1,
    )
    query: str = Field(
        ...,
        description="Natural language question or request about the project.",
        min_length=1,
    )
    use_llm: bool = Field(
        default=False,
        description="Whether to use an LLM for response phrasing (default is False: deterministic synthesis).",
    )

    @field_validator("project_id", "query")
    @classmethod
    def validate_non_blank(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Field must not be blank.")
        return cleaned


class AgentSourceItem(BaseModel):
    """
    Provenance reference to an authoritative Module 8 memory item.
    Strict schema: extra fields are forbidden.
    """

    model_config = ConfigDict(extra="forbid")

    memory_id: UUID | str = Field(
        ...,
        description="M8 memory item UUID.",
    )
    item_type: str = Field(
        ...,
        description="Type of memory item: task, decision, approval, communication, action.",
    )
    source_id: UUID | str = Field(
        ...,
        description="Upstream authoritative entity ID (e.g. task_id, decision_id, communication_id).",
    )
    communication_id: UUID | str = Field(
        ...,
        description="Original source communication ID.",
    )
    title: str = Field(
        ...,
        description="Title of the memory item.",
    )
    evidence: str | None = Field(
        default=None,
        description="Verbatim grounding evidence from source communication.",
    )
    score: float = Field(
        default=0.0,
        description="Relevance score from M8 retrieval.",
    )


class AgentResponse(BaseModel):
    """
    Canonical evidence-grounded agent query response.
    Strict schema: extra fields are forbidden.
    """

    model_config = ConfigDict(extra="forbid")

    project_id: str = Field(
        ...,
        description="Project ID queried.",
    )
    query: str = Field(
        ...,
        description="User's original natural language query.",
    )
    intent: QueryIntent = Field(
        ...,
        description="Classified query intent.",
    )
    answer: str = Field(
        ...,
        description="Evidence-backed natural answer.",
    )
    grounded: bool = Field(
        ...,
        description="True if the answer is grounded in retrieved M8 evidence; False if no evidence was found.",
    )
    result_count: int = Field(
        default=0,
        description="Count of supporting memory items found.",
    )
    sources: list[AgentSourceItem] = Field(
        default_factory=list,
        description="Explicit provenance references backing the answer.",
    )
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Server-side UTC timestamp of response generation.",
    )

    @field_validator("intent", mode="before")
    @classmethod
    def validate_intent(cls, v: str) -> str:
        if isinstance(v, str):
            normalized = v.strip().lower()
            if normalized in VALID_QUERY_INTENTS:
                return normalized
        return "general_memory"


class AgentQueryResponse(BaseModel):
    """Standard API response wrapper for agent query."""

    model_config = ConfigDict(extra="forbid")

    success: bool = True
    data: AgentResponse


class AgentErrorResponse(BaseModel):
    """Standard API error response for Module 9."""

    model_config = ConfigDict(extra="forbid")

    success: bool = False
    error: str
    detail: str | None = None
