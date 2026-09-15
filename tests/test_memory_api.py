"""
ArchScale — Module 8 Tests
API Integration tests for Module 8: Project Memory / Searchable Memory.
Covers indexing, deterministic search (POST & GET), overview stats,
task-focused retrieval, decision-focused retrieval, and full pipeline live flow.
"""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

import app.api.memory as memory_mod
from app.main import create_app
from app.models.communication import CommunicationRecord, SourceType
from app.models.decision import ExtractedDecision
from app.models.task import StructuredTask
from app.models.understanding import UnderstandingResult
from app.services.memory_service import MemoryService


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture()
def memory_client(tmp_path: Path) -> tuple[TestClient, MemoryService]:
    """TestClient wired to an isolated temporary SQLite database."""
    isolated_memory = MemoryService(db_path=tmp_path / "api_test_memory.db")
    app = create_app()

    orig_service = memory_mod._memory_service
    memory_mod._memory_service = isolated_memory
    app.dependency_overrides[memory_mod.get_memory_service] = lambda: isolated_memory

    with TestClient(app) as client:
        yield client, isolated_memory

    memory_mod._memory_service = orig_service


# ---------------------------------------------------------------------------
# API Tests
# ---------------------------------------------------------------------------


class TestMemoryAPIEndpoints:
    def test_health_check_includes_project_memory(self, memory_client: tuple[TestClient, MemoryService]) -> None:
        client, _ = memory_client
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "project_memory" in data["modules"]

    def test_post_index_item_success(self, memory_client: tuple[TestClient, MemoryService]) -> None:
        client, _ = memory_client
        payload = {
            "project_id": "proj-api-1",
            "item_type": "task",
            "source_id": "task-uuid-1",
            "communication_id": "comm-uuid-1",
            "title": "Send structural drawing",
            "content": "Architect will send the structural drawing by Friday.",
            "evidence": "Architect will send the structural drawing by Friday.",
            "metadata": {
                "responsible_party": "Architect",
                "status": "pending",
                "normalized_deadline": "2026-09-18",
            },
        }
        resp = client.post("/api/v1/memory/index", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["project_id"] == "proj-api-1"
        assert data["data"]["item_type"] == "task"
        assert data["data"]["source_id"] == "task-uuid-1"
        assert "memory_id" in data["data"]

    def test_post_index_idempotency(self, memory_client: tuple[TestClient, MemoryService]) -> None:
        client, _ = memory_client
        payload = {
            "project_id": "proj-api-idemp",
            "item_type": "decision",
            "source_id": "dec-unique-1",
            "communication_id": "comm-unique-1",
            "title": "Use double glazed glass",
            "content": "Double glazed glass agreed.",
            "evidence": "Double glazed glass agreed.",
            "metadata": {"status": "decided"},
        }
        # First post
        resp1 = client.post("/api/v1/memory/index", json=payload)
        assert resp1.status_code == 200
        mem_id_1 = resp1.json()["data"]["memory_id"]

        # Second post with updated title
        payload["title"] = "Use triple glazed glass"
        resp2 = client.post("/api/v1/memory/index", json=payload)
        assert resp2.status_code == 200
        mem_id_2 = resp2.json()["data"]["memory_id"]

        assert mem_id_1 == mem_id_2

    def test_post_index_validation_error(self, memory_client: tuple[TestClient, MemoryService]) -> None:
        client, _ = memory_client
        # Missing required title
        payload = {
            "project_id": "proj-fail",
            "item_type": "task",
            "source_id": "src-1",
            "communication_id": "comm-1",
            "content": "content",
        }
        resp = client.post("/api/v1/memory/index", json=payload)
        assert resp.status_code == 422

    def test_post_search_structured(self, memory_client: tuple[TestClient, MemoryService]) -> None:
        client, service = memory_client

        # Seed data
        task = StructuredTask(
            project_id="proj-search-api",
            communication_id="comm-api-1",
            action_id="act-api-1",
            title="Send structural drawing",
            description="Architect will send the structural drawing by Friday.",
            responsible_party="Architect",
            status="pending",
            evidence="Architect will send the structural drawing by Friday.",
        )
        service.index_task(task)

        # Search via POST
        search_req = {
            "project_id": "proj-search-api",
            "query": "structural drawing",
        }
        resp = client.post("/api/v1/memory/search", json=search_req)
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["result_count"] == 1
        assert body["data"]["results"][0]["title"] == "Send structural drawing"
        assert body["data"]["results"][0]["metadata"]["responsible_party"] == "Architect"

    def test_get_search_query_params(self, memory_client: tuple[TestClient, MemoryService]) -> None:
        client, service = memory_client

        dec = ExtractedDecision(
            decision_id="dec-get-1",
            item_type="approval",
            description="Client approved the kitchen layout.",
            subject="Kitchen",
            status="approved",
            evidence="Client approved the kitchen layout.",
            confidence=0.99,
        )
        service.index_decision(dec, "proj-get-search", "comm-get-1")

        # Search via GET
        resp = client.get("/api/v1/memory/search?project_id=proj-get-search&query=kitchen")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["result_count"] == 1
        assert body["data"]["results"][0]["item_type"] == "approval"

    def test_get_search_blank_project_id_returns_422(self, memory_client: tuple[TestClient, MemoryService]) -> None:
        client, _ = memory_client
        resp = client.get("/api/v1/memory/search?project_id=&query=test")
        assert resp.status_code == 422

    def test_get_project_overview_endpoint(self, memory_client: tuple[TestClient, MemoryService]) -> None:
        client, service = memory_client

        comm = CommunicationRecord(
            project_id="proj-stats",
            communication_id="comm-s1",
            source_type=SourceType.text,
            raw_content="Project kickoff meeting.",
        )
        service.index_communication(comm)

        task = StructuredTask(
            project_id="proj-stats",
            communication_id="comm-s1",
            action_id="act-s1",
            title="Setup boundary fencing",
            description="Contractor to setup fencing.",
            evidence="Setup boundary fencing.",
        )
        service.index_task(task)

        resp = client.get("/api/v1/memory/project/proj-stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        overview = data["data"]
        assert overview["project_id"] == "proj-stats"
        assert overview["communications"] == 1
        assert overview["tasks"] == 1
        assert overview["decisions"] == 0
        assert overview["approvals"] == 0
        assert overview["memory_items"] == 2

    def test_get_project_tasks_endpoint(self, memory_client: tuple[TestClient, MemoryService]) -> None:
        client, service = memory_client

        task1 = StructuredTask(
            project_id="proj-tasks-api",
            communication_id="comm-t1",
            action_id="act-t1",
            title="Draft elevation",
            description="Draft elevation plans.",
            responsible_party="Architect",
            status="pending",
            evidence="Draft elevation.",
        )
        task2 = StructuredTask(
            project_id="proj-tasks-api",
            communication_id="comm-t1",
            action_id="act-t2",
            title="Review elevation",
            description="Review elevation plans.",
            responsible_party="Client",
            status="completed",
            evidence="Review elevation.",
        )
        service.index_task(task1)
        service.index_task(task2)

        # All tasks
        resp_all = client.get("/api/v1/memory/project/proj-tasks-api/tasks")
        assert resp_all.status_code == 200
        assert resp_all.json()["data"]["task_count"] == 2

        # Filter by owner
        resp_owner = client.get("/api/v1/memory/project/proj-tasks-api/tasks?responsible_party=Architect")
        assert resp_owner.status_code == 200
        assert resp_owner.json()["data"]["task_count"] == 1
        assert resp_owner.json()["data"]["tasks"][0]["responsible_party"] == "Architect"

        # Filter by status
        resp_status = client.get("/api/v1/memory/project/proj-tasks-api/tasks?status=completed")
        assert resp_status.status_code == 200
        assert resp_status.json()["data"]["task_count"] == 1
        assert resp_status.json()["data"]["tasks"][0]["status"] == "completed"

    def test_get_project_decisions_endpoint(self, memory_client: tuple[TestClient, MemoryService]) -> None:
        client, service = memory_client

        dec = ExtractedDecision(
            decision_id="dec-d1",
            item_type="decision",
            description="Select Italian marble flooring.",
            subject="Flooring",
            status="decided",
            evidence="We decided on Italian marble flooring.",
            confidence=0.96,
        )
        appr = ExtractedDecision(
            decision_id="appr-d2",
            item_type="approval",
            description="Client approved plumbing layout.",
            subject="Plumbing",
            status="approved",
            evidence="Client approved plumbing layout.",
            confidence=0.99,
        )
        service.index_decision(dec, "proj-dec-api", "comm-d1")
        service.index_decision(appr, "proj-dec-api", "comm-d1")

        resp = client.get("/api/v1/memory/project/proj-dec-api/decisions")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["decision_count"] == 2
        items = data["decisions"]
        subjects = {item["subject"] for item in items}
        assert subjects == {"Flooring", "Plumbing"}


# ---------------------------------------------------------------------------
# Section 22: Critical Full Live Integration Test
# ---------------------------------------------------------------------------


class TestCriticalLiveIntegrationFlow:
    """
    Simulates live communication:
    "Client approved the revised kitchen layout.
    Architect will send the structural drawing by Friday.
    Britto Sir will review the drawing after it is received."

    Indexes resulting objects into M8 and executes required queries.
    """

    def test_live_communication_pipeline_and_search(
        self,
        memory_client: tuple[TestClient, MemoryService],
    ) -> None:
        client, service = memory_client
        project_id = "villa-live-proj"
        comm_id = "comm-live-uuid-001"

        # 1. Ingest communication (M1 representation)
        comm_record = CommunicationRecord(
            project_id=project_id,
            communication_id=comm_id,
            source_type=SourceType.text,
            raw_content=(
                "Client approved the revised kitchen layout.\n"
                "Architect will send the structural drawing by Friday.\n"
                "Britto Sir will review the drawing after it is received."
            ),
        )

        # 2. Understanding (M2 representation)
        understanding = UnderstandingResult(
            project_id=project_id,
            communication_id=comm_id,
            concise_summary="Client approved kitchen layout; structural drawing to be sent and reviewed.",
            detailed_summary=(
                "The client gave approval for the revised kitchen layout. "
                "The architect is scheduled to send structural drawings by Friday, "
                "which Britto Sir will review upon receipt."
            ),
            topics=["kitchen layout", "structural drawing", "drawing review"],
            stakeholders=["Client", "Architect", "Britto Sir"],
            communication_type="mixed",
        )

        # 3. Decision (M6 representation)
        decision_kitchen = ExtractedDecision(
            decision_id="dec-live-kitchen",
            item_type="approval",
            description="Client approved the revised kitchen layout.",
            subject="kitchen layout",
            status="approved",
            evidence="Client approved the revised kitchen layout.",
            confidence=0.99,
        )

        # 4. Structured Tasks (M7 representation)
        task_structural = StructuredTask(
            task_id=uuid4(),
            project_id=project_id,
            communication_id=comm_id,
            action_id="act-live-structural",
            title="Send the structural drawing",
            description="Architect will send the structural drawing by Friday.",
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

        task_britto_review = StructuredTask(
            task_id=uuid4(),
            project_id=project_id,
            communication_id=comm_id,
            action_id="act-live-britto",
            title="Review the drawing",
            description="Britto Sir will review the drawing after it is received.",
            responsible_party="Britto Sir",
            responsibility_type="person",
            deadline="after it is received",
            deadline_type="event_based",
            status="pending",
            priority="medium",
            evidence="Britto Sir will review the drawing after it is received.",
            decision_context=[],
        )

        # Index all items into Module 8
        indexed_items = service.index_project(
            project_id=project_id,
            communications=[comm_record],
            understandings=[understanding],
            decisions=[decision_kitchen],
            tasks=[task_structural, task_britto_review],
            communication_id=comm_id,
        )
        assert len(indexed_items) == 4

        # Also index a decoy item for another project to verify isolation
        service.index_task(
            StructuredTask(
                project_id="other-secret-project",
                communication_id="comm-other",
                action_id="act-other",
                title="Send the structural drawing for secret bunker",
                description="Classified blueprint.",
                responsible_party="Architect",
                evidence="Send the structural drawing for secret bunker.",
            )
        )

        # Query 1: "What did the client approve?"
        res1 = client.post(
            "/api/v1/memory/search",
            json={"project_id": project_id, "query": "what did the client approve?"},
        )
        assert res1.status_code == 200
        data1 = res1.json()["data"]
        assert data1["result_count"] >= 1
        top1 = data1["results"][0]
        assert top1["item_type"] == "approval"
        assert "kitchen layout" in top1["content"].lower()
        assert top1["evidence"] == "Client approved the revised kitchen layout."
        assert top1["communication_id"] == comm_id
        assert top1["source_id"] == "dec-live-kitchen"

        # Query 2: "structural drawing"
        res2 = client.post(
            "/api/v1/memory/search",
            json={"project_id": project_id, "query": "structural drawing"},
        )
        assert res2.status_code == 200
        data2 = res2.json()["data"]
        assert data2["result_count"] >= 1
        top2 = data2["results"][0]
        assert top2["title"] == "Send the structural drawing"
        assert top2["metadata"]["responsible_party"] == "Architect"
        assert top2["metadata"]["normalized_deadline"] == "2026-09-18"
        assert top2["evidence"] == "Architect will send the structural drawing by Friday."
        assert top2["communication_id"] == comm_id
        assert top2["source_id"] == str(task_structural.task_id)

        # Query 3: "Britto Sir"
        res3 = client.post(
            "/api/v1/memory/search",
            json={"project_id": project_id, "query": "Britto Sir"},
        )
        assert res3.status_code == 200
        data3 = res3.json()["data"]
        assert data3["result_count"] >= 1
        top3 = data3["results"][0]
        assert top3["title"] == "Review the drawing"
        assert top3["metadata"]["responsible_party"] == "Britto Sir"
        assert top3["evidence"] == "Britto Sir will review the drawing after it is received."
        assert top3["communication_id"] == comm_id
        assert top3["source_id"] == str(task_britto_review.task_id)

        # Query 4: "What tasks are assigned to the architect?"
        res4 = client.post(
            "/api/v1/memory/search",
            json={"project_id": project_id, "query": "What tasks are assigned to the architect?"},
        )
        assert res4.status_code == 200
        data4 = res4.json()["data"]
        assert data4["result_count"] >= 1
        top4 = data4["results"][0]
        assert top4["item_type"] == "task"
        assert top4["metadata"]["responsible_party"] == "Architect"

        # Project Isolation Check: Query in project_id cannot see "other-secret-project"
        res_isolation = client.post(
            "/api/v1/memory/search",
            json={"project_id": project_id, "query": "secret bunker"},
        )
        assert res_isolation.status_code == 200
        assert res_isolation.json()["data"]["result_count"] == 0
        assert len(res_isolation.json()["data"]["results"]) == 0

        # Verify overview endpoint for the project
        res_overview = client.get(f"/api/v1/memory/project/{project_id}")
        assert res_overview.status_code == 200
        overview = res_overview.json()["data"]
        assert overview["communications"] == 1
        assert overview["tasks"] == 2
        assert overview["approvals"] == 1
        assert overview["memory_items"] == 4
