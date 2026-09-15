"""
ArchScale — Module 8: Project Memory / Searchable Memory
Unit tests for MemoryService: indexing, idempotency, deterministic search, ranking, and provenance.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest

from app.models.communication import CommunicationRecord, SourceType
from app.models.decision import ExtractedDecision
from app.models.memory import MemorySearchRequest
from app.models.task import StructuredTask
from app.models.understanding import UnderstandingResult
from app.services.memory_service import MemoryService, MemoryValidationError


@pytest.fixture()
def memory_service(tmp_path: Path) -> MemoryService:
    """Provide a MemoryService instance backed by an isolated temporary SQLite DB."""
    db_file = tmp_path / "test_memory.db"
    return MemoryService(db_path=db_file)


# ---------------------------------------------------------------------------
# Indexing Tests
# ---------------------------------------------------------------------------


class TestMemoryIndexing:
    def test_index_communication_basic(self, memory_service: MemoryService) -> None:
        record = CommunicationRecord(
            project_id="villa-proj",
            communication_id="comm-101",
            source_type=SourceType.text,
            raw_content="Excavation completed on site yesterday.",
        )
        item = memory_service.index_communication(record)

        assert item.project_id == "villa-proj"
        assert item.item_type == "communication"
        assert item.source_id == "comm-101"
        assert item.communication_id == "comm-101"
        assert "Excavation completed" in item.title
        assert item.content == "Excavation completed on site yesterday."
        assert item.metadata["source_type"] == "text"

    def test_index_communication_with_understanding(self, memory_service: MemoryService) -> None:
        record = CommunicationRecord(
            project_id="villa-proj",
            communication_id="comm-102",
            source_type=SourceType.text,
            raw_content="Client approved the kitchen layout. Architect to finalize drawings.",
        )
        understanding = UnderstandingResult(
            project_id="villa-proj",
            communication_id="comm-102",
            concise_summary="Kitchen layout approved and drawing finalization requested.",
            detailed_summary="The client approved the kitchen layout during the design review. Architect will proceed.",
            topics=["kitchen layout", "architectural drawings"],
            stakeholders=["Client", "Architect"],
            communication_type="approval",
        )
        item = memory_service.index_communication(record, understanding)

        assert item.title == "Kitchen layout approved and drawing finalization requested."
        assert "design review" in item.content
        assert item.metadata["topics"] == ["kitchen layout", "architectural drawings"]
        assert item.metadata["stakeholders"] == ["Client", "Architect"]
        assert item.metadata["communication_type"] == "approval"

    def test_index_task(self, memory_service: MemoryService) -> None:
        task = StructuredTask(
            task_id=uuid4(),
            project_id="villa-proj",
            communication_id="comm-103",
            action_id="act-1",
            title="Send structural drawing",
            description="Architect must send the structural drawing by Friday.",
            responsible_party="Architect",
            responsibility_type="role",
            deadline="Friday",
            deadline_type="relative_day",
            normalized_deadline="2026-09-18",
            status="pending",
            priority="high",
            evidence="Architect will send the structural drawing by Friday.",
            decision_context=["Client approved the revised kitchen layout."],
        )
        item = memory_service.index_task(task)

        assert item.project_id == "villa-proj"
        assert item.item_type == "task"
        assert item.source_id == str(task.task_id)
        assert item.communication_id == "comm-103"
        assert item.title == "Send structural drawing"
        assert item.content == task.description
        assert item.evidence == task.evidence
        assert item.metadata["responsible_party"] == "Architect"
        assert item.metadata["status"] == "pending"
        assert item.metadata["normalized_deadline"] == "2026-09-18"

    def test_index_decision_and_approval(self, memory_service: MemoryService) -> None:
        dec = ExtractedDecision(
            decision_id="dec-201",
            item_type="decision",
            description="Use raft foundation for the villa.",
            subject="Foundation",
            status="decided",
            evidence="We decided to proceed with raft foundation.",
            confidence=0.95,
        )
        item_dec = memory_service.index_decision(dec, project_id="villa-proj", communication_id="comm-104")
        assert item_dec.item_type == "decision"
        assert item_dec.title == "Foundation: Use raft foundation for the villa."
        assert item_dec.source_id == "dec-201"

        appr = ExtractedDecision(
            decision_id="appr-202",
            item_type="approval",
            description="Client approved the revised kitchen layout.",
            subject="Kitchen layout",
            status="approved",
            evidence="Client approved the revised kitchen layout.",
            confidence=0.98,
        )
        item_appr = memory_service.index_decision(appr, project_id="villa-proj", communication_id="comm-104")
        assert item_appr.item_type == "approval"
        assert item_appr.metadata["status"] == "approved"

    def test_index_project_multiple_objects(self, memory_service: MemoryService) -> None:
        comm = CommunicationRecord(
            project_id="proj-multi",
            communication_id="comm-m1",
            source_type=SourceType.text,
            raw_content="Meeting notes text.",
        )
        dec = ExtractedDecision(
            decision_id="dec-m1",
            item_type="decision",
            description="Floor plan finalized.",
            status="decided",
            evidence="Floor plan is finalized.",
            confidence=0.9,
        )
        task = StructuredTask(
            project_id="proj-multi",
            communication_id="comm-m1",
            action_id="act-m1",
            title="Prepare 3D model",
            description="Prepare 3D model of floor plan.",
            evidence="Prepare 3D model.",
        )

        indexed = memory_service.index_project(
            project_id="proj-multi",
            communications=[comm],
            decisions=[dec],
            tasks=[task],
            communication_id="comm-m1",
        )
        assert len(indexed) == 3
        types = {item.item_type for item in indexed}
        assert types == {"communication", "decision", "task"}


# ---------------------------------------------------------------------------
# Idempotency Tests
# ---------------------------------------------------------------------------


class TestMemoryIdempotency:
    def test_repeated_task_indexing_does_not_duplicate(self, memory_service: MemoryService) -> None:
        task_id = uuid4()
        task = StructuredTask(
            task_id=task_id,
            project_id="idemp-proj",
            communication_id="comm-idem-1",
            action_id="act-idem",
            title="Check soil report",
            description="Initial description",
            evidence="Check the soil report tomorrow.",
            status="pending",
        )

        # First indexing
        item1 = memory_service.index_task(task)
        memory_id_1 = item1.memory_id
        created_at_1 = item1.created_at

        # Second indexing with updated title/description
        task_updated = StructuredTask(
            task_id=task_id,
            project_id="idemp-proj",
            communication_id="comm-idem-1",
            action_id="act-idem",
            title="Check soil report thoroughly",
            description="Updated description after follow-up",
            evidence="Check the soil report tomorrow.",
            status="in_progress",
        )
        item2 = memory_service.index_task(task_updated)

        # Same memory ID and created_at preserved
        assert item2.memory_id == memory_id_1
        assert item2.created_at == created_at_1
        assert item2.title == "Check soil report thoroughly"
        assert item2.content == "Updated description after follow-up"
        assert item2.metadata["status"] == "in_progress"

        # Verify only 1 record exists in DB
        overview = memory_service.get_project_memory("idemp-proj")
        assert overview.tasks == 1
        assert overview.memory_items == 1

    def test_repeated_decision_indexing_does_not_duplicate(self, memory_service: MemoryService) -> None:
        dec = ExtractedDecision(
            decision_id="dec-same",
            item_type="decision",
            description="Approved budget $50k",
            evidence="Budget $50k agreed.",
            confidence=0.88,
        )
        item1 = memory_service.index_decision(dec, "idemp-proj-2", "comm-1")
        item2 = memory_service.index_decision(dec, "idemp-proj-2", "comm-1")

        assert item1.memory_id == item2.memory_id
        overview = memory_service.get_project_memory("idemp-proj-2")
        assert overview.decisions == 1
        assert overview.memory_items == 1


# ---------------------------------------------------------------------------
# Project Isolation Tests
# ---------------------------------------------------------------------------


class TestProjectIsolation:
    def test_search_strictly_isolated_between_projects(self, memory_service: MemoryService) -> None:
        # Index into Project A
        task_a = StructuredTask(
            project_id="project-A",
            communication_id="comm-A",
            action_id="act-A",
            title="Secret confidential plan for Project A",
            description="Detailed specifications for Project A.",
            evidence="Confidential plan.",
        )
        memory_service.index_task(task_a)

        # Index into Project B
        task_b = StructuredTask(
            project_id="project-B",
            communication_id="comm-B",
            action_id="act-B",
            title="Public plan for Project B",
            description="Specifications for Project B.",
            evidence="Public plan.",
        )
        memory_service.index_task(task_b)

        # Search in Project B for terms present in Project A
        search_b = memory_service.search(
            MemorySearchRequest(project_id="project-B", query="Secret confidential plan")
        )
        assert search_b.result_count == 0
        assert len(search_b.results) == 0

        # Search in Project A for Project A terms
        search_a = memory_service.search(
            MemorySearchRequest(project_id="project-A", query="Secret confidential plan")
        )
        assert search_a.result_count == 1
        assert search_a.results[0].project_id == "project-A"
        assert search_a.results[0].title == "Secret confidential plan for Project A"


# ---------------------------------------------------------------------------
# Deterministic Search & Ranking Tests
# ---------------------------------------------------------------------------


class TestDeterministicSearchAndRanking:
    @pytest.fixture(autouse=True)
    def setup_corpus(self, memory_service: MemoryService) -> None:
        # Task 1: Structural drawing
        self.task1 = StructuredTask(
            project_id="villa-search",
            communication_id="comm-live-1",
            action_id="act-1",
            title="Send the structural drawing",
            description="Architect will send the structural drawing by Friday.",
            responsible_party="Architect",
            responsibility_type="role",
            deadline="Friday",
            normalized_deadline="2026-09-18",
            status="pending",
            priority="high",
            evidence="Architect will send the structural drawing by Friday.",
        )
        memory_service.index_task(self.task1)

        # Task 2: Review drawing
        self.task2 = StructuredTask(
            project_id="villa-search",
            communication_id="comm-live-1",
            action_id="act-2",
            title="Review the drawing",
            description="Britto Sir will review the drawing after it is received.",
            responsible_party="Britto Sir",
            responsibility_type="person",
            status="pending",
            evidence="Britto Sir will review the drawing after it is received.",
        )
        memory_service.index_task(self.task2)

        # Approval: Kitchen layout
        self.appr = ExtractedDecision(
            decision_id="dec-appr-1",
            item_type="approval",
            description="Client approved the revised kitchen layout.",
            subject="Kitchen layout",
            status="approved",
            evidence="Client approved the revised kitchen layout.",
            confidence=0.99,
        )
        memory_service.index_decision(self.appr, "villa-search", "comm-live-1")

    def test_query_what_did_client_approve(self, memory_service: MemoryService) -> None:
        res = memory_service.search(
            MemorySearchRequest(project_id="villa-search", query="What did the client approve?")
        )
        assert res.result_count >= 1
        top = res.results[0]
        assert top.item_type == "approval"
        assert "kitchen layout" in top.content.lower()
        assert top.communication_id == "comm-live-1"
        assert top.evidence == "Client approved the revised kitchen layout."

    def test_query_structural_drawing(self, memory_service: MemoryService) -> None:
        res = memory_service.search(
            MemorySearchRequest(project_id="villa-search", query="structural drawing")
        )
        assert res.result_count >= 1
        top = res.results[0]
        assert top.title == "Send the structural drawing"
        assert top.metadata["responsible_party"] == "Architect"
        assert top.metadata["normalized_deadline"] == "2026-09-18"
        assert top.evidence == "Architect will send the structural drawing by Friday."
        assert top.communication_id == "comm-live-1"

    def test_query_britto_sir(self, memory_service: MemoryService) -> None:
        res = memory_service.search(
            MemorySearchRequest(project_id="villa-search", query="Britto Sir")
        )
        assert res.result_count >= 1
        top = res.results[0]
        assert top.title == "Review the drawing"
        assert top.metadata["responsible_party"] == "Britto Sir"
        assert "Britto Sir will review the drawing" in top.evidence

    def test_exact_phrase_ranks_above_single_token(self, memory_service: MemoryService) -> None:
        # Index another item that only mentions "drawing" but not "structural drawing"
        task_other = StructuredTask(
            project_id="villa-search",
            communication_id="comm-live-1",
            action_id="act-3",
            title="Sketch interior drawing concepts",
            description="General drawing sketches for living room.",
            evidence="Interior drawing concepts.",
        )
        memory_service.index_task(task_other)

        res = memory_service.search(
            MemorySearchRequest(project_id="villa-search", query="structural drawing")
        )
        # Structural drawing task should rank higher due to exact phrase match
        assert res.results[0].title == "Send the structural drawing"
        assert res.results[0].score > res.results[1].score

    def test_item_type_filter(self, memory_service: MemoryService) -> None:
        # Search only tasks
        res_tasks = memory_service.search(
            MemorySearchRequest(project_id="villa-search", query="kitchen", item_type="task")
        )
        for r in res_tasks.results:
            assert r.item_type == "task"

        # Search only approvals
        res_approvals = memory_service.search(
            MemorySearchRequest(project_id="villa-search", query="kitchen", item_type="approval")
        )
        assert len(res_approvals.results) == 1
        assert res_approvals.results[0].item_type == "approval"

    def test_owner_filter(self, memory_service: MemoryService) -> None:
        res = memory_service.search(
            MemorySearchRequest(project_id="villa-search", responsible_party="Architect")
        )
        assert len(res.results) == 1
        assert res.results[0].title == "Send the structural drawing"

    def test_status_filter(self, memory_service: MemoryService) -> None:
        res = memory_service.search(
            MemorySearchRequest(project_id="villa-search", status="approved")
        )
        assert len(res.results) == 1
        assert res.results[0].metadata["status"] == "approved"

    def test_empty_search_returns_zero_without_hallucination(self, memory_service: MemoryService) -> None:
        res = memory_service.search(
            MemorySearchRequest(project_id="villa-search", query="nonexistent_alien_technology_xyz")
        )
        assert res.result_count == 0
        assert res.results == []

    def test_blank_query_returns_all_items_in_project(self, memory_service: MemoryService) -> None:
        res = memory_service.search(
            MemorySearchRequest(project_id="villa-search", query="")
        )
        assert res.result_count == 3


# ---------------------------------------------------------------------------
# Retrieval Views & Overview Tests
# ---------------------------------------------------------------------------


class TestRetrievalViews:
    def test_get_project_memory_overview(self, memory_service: MemoryService) -> None:
        overview = memory_service.get_project_memory("villa-search-empty")
        assert overview.communications == 0
        assert overview.tasks == 0
        assert overview.decisions == 0
        assert overview.approvals == 0
        assert overview.memory_items == 0

    def test_get_project_tasks_and_decisions(self, memory_service: MemoryService) -> None:
        task = StructuredTask(
            project_id="villa-view",
            communication_id="comm-v1",
            action_id="act-v1",
            title="Install electrical wiring",
            description="Install wiring in ground floor.",
            responsible_party="Electrician",
            status="in_progress",
            evidence="Install electrical wiring.",
        )
        memory_service.index_task(task)

        dec = ExtractedDecision(
            decision_id="dec-v1",
            item_type="decision",
            description="Selected warm LED lighting.",
            subject="Lighting",
            status="decided",
            evidence="Selected warm LED lighting.",
            confidence=0.92,
        )
        memory_service.index_decision(dec, "villa-view", "comm-v1")

        # Retrieve tasks
        tasks_data = memory_service.get_project_tasks("villa-view")
        assert tasks_data.task_count == 1
        assert tasks_data.tasks[0].title == "Install electrical wiring"
        assert tasks_data.tasks[0].responsible_party == "Electrician"

        # Filter tasks by status
        tasks_filtered = memory_service.get_project_tasks("villa-view", status="in_progress")
        assert tasks_filtered.task_count == 1
        tasks_none = memory_service.get_project_tasks("villa-view", status="completed")
        assert tasks_none.task_count == 0

        # Retrieve decisions
        dec_data = memory_service.get_project_decisions("villa-view")
        assert dec_data.decision_count == 1
        assert dec_data.decisions[0].subject == "Lighting"
        assert dec_data.decisions[0].description == "Selected warm LED lighting."
