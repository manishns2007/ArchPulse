"""
ArchScale — Module 9 Tests
API Integration tests for Module 9: Agentic Project Query & User Interaction.
Covers POST /api/v1/agent/query, GET /api/v1/agent/query, health check,
and complete full-pipeline integration (M1 → M9).
"""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

import app.api.agent as agent_mod
import app.api.memory as memory_mod
from app.main import create_app
from app.models.communication import CommunicationRecord, SourceType
from app.models.decision import ExtractedDecision
from app.models.task import StructuredTask
from app.models.understanding import UnderstandingResult
from app.services.agent_service import AgentService, UNGROUNDED_MESSAGE
from app.services.memory_service import MemoryService


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture()
def agent_client(tmp_path: Path) -> tuple[TestClient, AgentService, MemoryService]:
    """TestClient wired to isolated MemoryService and AgentService."""
    isolated_memory = MemoryService(db_path=tmp_path / "agent_api_test.db")
    isolated_agent = AgentService(memory_service=isolated_memory)

    app = create_app()

    orig_mem_svc = memory_mod._memory_service
    orig_agent_svc = agent_mod._agent_service

    memory_mod._memory_service = isolated_memory
    agent_mod._agent_service = isolated_agent

    app.dependency_overrides[memory_mod.get_memory_service] = lambda: isolated_memory
    app.dependency_overrides[agent_mod.get_agent_service] = lambda: isolated_agent

    with TestClient(app) as client:
        yield client, isolated_agent, isolated_memory

    memory_mod._memory_service = orig_mem_svc
    agent_mod._agent_service = orig_agent_svc


# ---------------------------------------------------------------------------
# API Endpoint Tests
# ---------------------------------------------------------------------------


class TestAgentAPIEndpoints:
    def test_health_check_includes_agent_query(
        self,
        agent_client: tuple[TestClient, AgentService, MemoryService],
    ) -> None:
        client, _, _ = agent_client
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "agent_query" in data["modules"]

    def test_post_agent_query_grounded_success(
        self,
        agent_client: tuple[TestClient, AgentService, MemoryService],
    ) -> None:
        client, _, memory = agent_client

        # Seed data
        comm_id = str(uuid4())
        appr = ExtractedDecision(
            decision_id="dec-test-1",
            item_type="approval",
            description="Client approved revised kitchen layout.",
            subject="kitchen layout",
            status="approved",
            evidence="Client approved revised kitchen layout.",
            confidence=0.98,
        )
        memory.index_decision(appr, "proj-api-agent", comm_id)

        resp = client.post(
            "/api/v1/agent/query",
            json={
                "project_id": "proj-api-agent",
                "query": "What did the client approve?",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        agent_res = data["data"]
        assert agent_res["grounded"] is True
        assert agent_res["result_count"] >= 1
        assert "kitchen layout" in agent_res["answer"].lower()
        assert len(agent_res["sources"]) >= 1
        assert agent_res["sources"][0]["item_type"] == "approval"

    def test_post_agent_query_ungrounded_fallback(
        self,
        agent_client: tuple[TestClient, AgentService, MemoryService],
    ) -> None:
        client, _, _ = agent_client

        resp = client.post(
            "/api/v1/agent/query",
            json={
                "project_id": "empty-proj",
                "query": "What are the structural details?",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        agent_res = data["data"]
        assert agent_res["grounded"] is False
        assert agent_res["result_count"] == 0
        assert agent_res["answer"] == UNGROUNDED_MESSAGE

    def test_post_agent_query_validation_error(
        self,
        agent_client: tuple[TestClient, AgentService, MemoryService],
    ) -> None:
        client, _, _ = agent_client

        # Missing query field
        resp = client.post(
            "/api/v1/agent/query",
            json={"project_id": "proj-1"},
        )
        assert resp.status_code == 422

    def test_get_agent_query_success(
        self,
        agent_client: tuple[TestClient, AgentService, MemoryService],
    ) -> None:
        client, _, memory = agent_client

        memory.index_task(
            StructuredTask(
                project_id="proj-get-agent",
                communication_id="comm-g",
                action_id="act-g",
                title="Send the structural drawing",
                description="Architect to send drawing by Friday.",
                responsible_party="Architect",
                deadline="Friday",
                normalized_deadline="2026-09-18",
                evidence="Architect will send the structural drawing by Friday.",
            )
        )

        resp = client.get(
            "/api/v1/agent/query?project_id=proj-get-agent&query=What%20does%20the%20architect%20need%20to%20do%3F"
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["grounded"] is True
        assert "Send the structural drawing" in body["data"]["answer"]


# ---------------------------------------------------------------------------
# Full End-to-End Pipeline Integration Test (M1 → M9)
# ---------------------------------------------------------------------------


class TestFullPipelineM1ToM9:
    """
    Validates complete pipeline from ingested communication to M9 agent response.
    """

    def test_full_pipeline_live_scenario(
        self,
        agent_client: tuple[TestClient, AgentService, MemoryService],
    ) -> None:
        client, _, memory = agent_client
        project_id = "villa-e2e"
        comm_id = "comm-e2e-123"

        # 1. Ingestion (M1 representation)
        comm = CommunicationRecord(
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
        und = UnderstandingResult(
            project_id=project_id,
            communication_id=comm_id,
            concise_summary="Client approved kitchen layout; structural drawing to be sent and reviewed.",
            detailed_summary="The client approved the kitchen layout. Architect sends drawing by Friday. Britto Sir reviews.",
            topics=["kitchen layout", "structural drawing", "drawing review"],
            stakeholders=["Client", "Architect", "Britto Sir"],
            communication_type="mixed",
            important_context=["Review scheduled after receipt."],
        )

        # 3. Decision (M6 representation)
        dec = ExtractedDecision(
            decision_id="dec-e2e-kitchen",
            item_type="approval",
            description="Client approved the revised kitchen layout.",
            subject="kitchen layout",
            status="approved",
            evidence="Client approved the revised kitchen layout.",
            confidence=0.99,
        )

        # 4. Structured Tasks (M7 representation)
        task_struct = StructuredTask(
            task_id=uuid4(),
            project_id=project_id,
            communication_id=comm_id,
            action_id="act-e2e-struct",
            title="Send the structural drawing",
            description="Architect will send the structural drawing by Friday.",
            responsible_party="Architect",
            responsibility_type="role",
            deadline="Friday",
            normalized_deadline="2026-09-18",
            status="pending",
            priority="high",
            evidence="Architect will send the structural drawing by Friday.",
            decision_context=["Client approved the revised kitchen layout."],
        )

        task_britto = StructuredTask(
            task_id=uuid4(),
            project_id=project_id,
            communication_id=comm_id,
            action_id="act-e2e-britto",
            title="Review the drawing",
            description="Britto Sir will review the drawing after it is received.",
            responsible_party="Britto Sir",
            responsibility_type="person",
            deadline="after it is received",
            status="pending",
            priority="medium",
            evidence="Britto Sir will review the drawing after it is received.",
        )

        # 5. Index into M8 Project Memory
        memory.index_project(
            project_id=project_id,
            communications=[comm],
            understandings=[und],
            decisions=[dec],
            tasks=[task_struct, task_britto],
            communication_id=comm_id,
        )

        # 6. Query 1: "What did the client approve?"
        r1 = client.post(
            "/api/v1/agent/query",
            json={"project_id": project_id, "query": "What did the client approve?"},
        )
        assert r1.status_code == 200
        d1 = r1.json()["data"]
        assert d1["grounded"] is True
        assert "kitchen layout" in d1["answer"].lower()
        assert d1["sources"][0]["evidence"] == "Client approved the revised kitchen layout."

        # 7. Query 2: "What does the architect need to do?"
        r2 = client.post(
            "/api/v1/agent/query",
            json={"project_id": project_id, "query": "What does the architect need to do?"},
        )
        assert r2.status_code == 200
        d2 = r2.json()["data"]
        assert d2["grounded"] is True
        assert "Send the structural drawing" in d2["answer"]

        # 8. Query 3: "What tasks are assigned to Britto Sir?"
        r3 = client.post(
            "/api/v1/agent/query",
            json={"project_id": project_id, "query": "What tasks are assigned to Britto Sir?"},
        )
        assert r3.status_code == 200
        d3 = r3.json()["data"]
        assert d3["grounded"] is True
        assert "Review the drawing" in d3["answer"]

        # 9. Query 4: "Give me the current project status."
        r4 = client.post(
            "/api/v1/agent/query",
            json={"project_id": project_id, "query": "Give me the current project status."},
        )
        assert r4.status_code == 200
        d4 = r4.json()["data"]
        assert d4["grounded"] is True
        assert "Project Overview" in d4["answer"]

        # 10. Query 5: Unmatched query returns ungrounded zero-result
        r5 = client.post(
            "/api/v1/agent/query",
            json={"project_id": project_id, "query": "Is there a helicopter landing pad on the roof?"},
        )
        assert r5.status_code == 200
        d5 = r5.json()["data"]
        assert d5["grounded"] is False
        assert d5["result_count"] == 0
        assert d5["answer"] == UNGROUNDED_MESSAGE
