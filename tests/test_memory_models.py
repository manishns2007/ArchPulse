"""
ArchScale — Module 8: Project Memory / Searchable Memory
Tests for Project Memory Pydantic v2 data models.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from app.models.memory import (
    DecisionItemData,
    MemoryIndexItemRequest,
    MemoryItemType,
    MemorySearchRequest,
    MemorySearchResult,
    MemorySearchResultItem,
    ProjectDecisionsData,
    ProjectMemoryItem,
    ProjectMemoryOverview,
    ProjectTasksData,
    VALID_MEMORY_ITEM_TYPES,
)


class TestProjectMemoryItemModel:
    """Test suite for ProjectMemoryItem model constraints and validation."""

    def test_valid_memory_item_creation(self) -> None:
        item = ProjectMemoryItem(
            project_id="proj-100",
            item_type="task",
            source_id="task-123",
            communication_id="comm-456",
            title="Send structural drawing",
            content="Architect to send drawing by Friday",
            evidence="Architect will send the structural drawing by Friday.",
            metadata={"responsible_party": "Architect"},
        )
        assert isinstance(item.memory_id, UUID)
        assert item.project_id == "proj-100"
        assert item.item_type == "task"
        assert item.source_id == "task-123"
        assert item.communication_id == "comm-456"
        assert item.title == "Send structural drawing"
        assert item.content == "Architect to send drawing by Friday"
        assert item.evidence == "Architect will send the structural drawing by Friday."
        assert item.metadata == {"responsible_party": "Architect"}
        assert isinstance(item.created_at, datetime)
        assert isinstance(item.updated_at, datetime)

    def test_extra_fields_forbidden(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            ProjectMemoryItem(
                project_id="proj-100",
                item_type="task",
                source_id="task-123",
                communication_id="comm-456",
                title="Send structural drawing",
                content="Content",
                extra_forbidden_field="disallowed",  # type: ignore[call-arg]
            )
        assert "extra_forbidden_field" in str(exc_info.value)

    def test_blank_project_id_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ProjectMemoryItem(
                project_id="   ",
                item_type="task",
                source_id="task-123",
                communication_id="comm-456",
                title="Title",
                content="Content",
            )

    def test_blank_title_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ProjectMemoryItem(
                project_id="proj-100",
                item_type="task",
                source_id="task-123",
                communication_id="comm-456",
                title="   ",
                content="Content",
            )

    def test_blank_content_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ProjectMemoryItem(
                project_id="proj-100",
                item_type="task",
                source_id="task-123",
                communication_id="comm-456",
                title="Title",
                content="",
            )

    def test_invalid_item_type_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ProjectMemoryItem(
                project_id="proj-100",
                item_type="invalid_type",  # type: ignore[arg-type]
                source_id="task-123",
                communication_id="comm-456",
                title="Title",
                content="Content",
            )

    def test_all_valid_item_types_accepted(self) -> None:
        for it in VALID_MEMORY_ITEM_TYPES:
            item = ProjectMemoryItem(
                project_id="proj-100",
                item_type=it,  # type: ignore[arg-type]
                source_id="source-1",
                communication_id="comm-1",
                title=f"Title {it}",
                content=f"Content {it}",
            )
            assert item.item_type == it


class TestMemorySearchRequestModel:
    """Test suite for MemorySearchRequest."""

    def test_valid_search_request(self) -> None:
        req = MemorySearchRequest(
            project_id="proj-alpha",
            query="structural drawing",
            item_type="task",
            responsible_party="Architect",
            status="pending",
            deadline="Friday",
            limit=10,
        )
        assert req.project_id == "proj-alpha"
        assert req.query == "structural drawing"
        assert req.item_type == "task"
        assert req.responsible_party == "Architect"
        assert req.status == "pending"
        assert req.deadline == "Friday"
        assert req.limit == 10

    def test_blank_project_id_rejected(self) -> None:
        with pytest.raises(ValidationError):
            MemorySearchRequest(project_id="   ")

    def test_extra_fields_forbidden(self) -> None:
        with pytest.raises(ValidationError):
            MemorySearchRequest(
                project_id="proj-alpha",
                unexpected_field="disallowed",  # type: ignore[call-arg]
            )

    def test_limit_validation(self) -> None:
        with pytest.raises(ValidationError):
            MemorySearchRequest(project_id="proj-alpha", limit=0)
        with pytest.raises(ValidationError):
            MemorySearchRequest(project_id="proj-alpha", limit=201)


class TestMemorySearchResultModels:
    """Test suite for MemorySearchResultItem and MemorySearchResult."""

    def test_result_item_and_container(self) -> None:
        item = MemorySearchResultItem(
            memory_id="mem-1",
            project_id="proj-1",
            item_type="approval",
            source_id="dec-1",
            communication_id="comm-1",
            title="Client approved layout",
            content="Client approved the revised layout.",
            evidence="Client approved the layout.",
            metadata={"status": "approved"},
            score=12.5,
            retrieval_mode="keyword",
        )
        res = MemorySearchResult(
            project_id="proj-1",
            query="layout approval",
            results=[item],
            result_count=1,
            retrieval_mode="keyword",
        )
        assert res.project_id == "proj-1"
        assert res.result_count == 1
        assert res.results[0].title == "Client approved layout"
        assert res.results[0].score == 12.5


class TestOverviewAndEntityDataModels:
    """Test overview and view models."""

    def test_project_memory_overview(self) -> None:
        overview = ProjectMemoryOverview(
            project_id="proj-1",
            communications=2,
            tasks=5,
            decisions=3,
            approvals=1,
            memory_items=11,
        )
        assert overview.project_id == "proj-1"
        assert overview.memory_items == 11

    def test_decision_item_data(self) -> None:
        d = DecisionItemData(
            decision_id="dec-123",
            item_type="decision",
            description="Foundation choice",
            subject="Foundation",
            status="decided",
            evidence="We decided on raft foundation.",
            communication_id="comm-456",
        )
        assert d.decision_id == "dec-123"
        assert d.subject == "Foundation"
