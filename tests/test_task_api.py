"""
ArchScale — Module 7 Tests
Integration tests for the Structured Task API endpoint: POST /api/v1/tasks/structure.
"""

from __future__ import annotations

from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

import app.api.ingestion as ingestion_mod
import app.api.tasks as tasks_mod
from app.llm.provider import FakeLLMProvider
from app.main import create_app
from app.models.action_extraction import ExtractedAction
from app.models.deadline import DeadlineAssignment
from app.models.decision import ExtractedDecision
from app.models.responsibility import ResponsibilityAssignment
from app.services.action_extraction_service import ActionExtractionService
from app.services.deadline_service import DeadlineService
from app.services.decision_service import DecisionService
from app.services.ingestion_service import IngestionService
from app.services.responsibility_service import ResponsibilityService
from app.services.task_service import TaskService
from app.services.understanding_service import (
    CommunicationUnderstandingService,
    UnderstandingProviderError,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def task_client(tmp_storage: dict[str, Path]) -> TestClient:
    """
    TestClient configured with isolated services backed by temporary storage
    and FakeLLMProvider instances for fast, deterministic execution.
    """
    isolated_ingestion = IngestionService(
        raw_path=tmp_storage["raw"],
        processed_path=tmp_storage["processed"],
    )
    fake_llm = FakeLLMProvider()

    isolated_und = CommunicationUnderstandingService(llm_provider=fake_llm)
    isolated_act = ActionExtractionService(llm_provider=fake_llm)
    isolated_resp = ResponsibilityService(llm_provider=fake_llm)
    isolated_dl = DeadlineService(llm_provider=fake_llm)
    isolated_dec = DecisionService(llm_provider=fake_llm)
    isolated_task = TaskService()

    app = create_app()

    # Save originals
    orig_ingest = ingestion_mod._service
    orig_task_ingest = tasks_mod._ingestion_service
    orig_task_und = tasks_mod._understanding_service
    orig_task_act = tasks_mod._action_extraction_service
    orig_task_resp = tasks_mod._responsibility_service
    orig_task_dl = tasks_mod._deadline_service
    orig_task_dec = tasks_mod._decision_service
    orig_task_svc = tasks_mod._task_service

    # Patch
    ingestion_mod._service = isolated_ingestion
    tasks_mod._ingestion_service = isolated_ingestion
    tasks_mod._understanding_service = isolated_und
    tasks_mod._action_extraction_service = isolated_act
    tasks_mod._responsibility_service = isolated_resp
    tasks_mod._deadline_service = isolated_dl
    tasks_mod._decision_service = isolated_dec
    tasks_mod._task_service = isolated_task

    with TestClient(app) as client:
        yield client

    # Restore originals
    ingestion_mod._service = orig_ingest
    tasks_mod._ingestion_service = orig_task_ingest
    tasks_mod._understanding_service = orig_task_und
    tasks_mod._action_extraction_service = orig_task_act
    tasks_mod._responsibility_service = orig_task_resp
    tasks_mod._deadline_service = orig_task_dl
    tasks_mod._decision_service = orig_task_dec
    tasks_mod._task_service = orig_task_svc


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestTaskAPI:
    def test_structure_tasks_full_pipeline_success(self, task_client: TestClient) -> None:
        # Step 1: Ingest communication
        ingest_resp = task_client.post(
            "/api/v1/ingest/text",
            json={
                "project_id": "proj-villa",
                "source_type": "text",
                "content": (
                    "Client approved the revised kitchen layout. "
                    "Architect will send the structural drawing by Friday. "
                    "Britto Sir will review the drawing after it is received."
                ),
            },
        )
        assert ingest_resp.status_code == 201
        comm_id = ingest_resp.json()["data"]["communication_id"]

        # Step 2: Call Task Structure API
        resp = task_client.post(
            "/api/v1/tasks/structure",
            json={"communication_id": comm_id},
        )
        assert resp.status_code == 200
        body = resp.json()

        assert body["success"] is True
        data = body["data"]
        assert data["project_id"] == "proj-villa"
        assert data["communication_id"] == comm_id
        assert "tasks" in data
        assert isinstance(data["tasks"], list)
        assert data["task_count"] == len(data["tasks"])

        # Check default task structure
        for task in data["tasks"]:
            assert "task_id" in task
            # Verify valid UUID4
            uuid_obj = UUID(task["task_id"])
            assert uuid_obj.version == 4
            assert task["project_id"] == "proj-villa"
            assert task["communication_id"] == comm_id
            assert task["status"] == "pending"
            assert task["priority"] == "unspecified"
            assert isinstance(task["title"], str)
            assert len(task["title"]) > 0
            assert isinstance(task["description"], str)
            assert len(task["description"]) > 0
            assert "evidence" in task
            assert "decision_context" in task

    def test_structure_tasks_with_explicit_overrides_in_request(self, task_client: TestClient) -> None:
        # Step 1: Ingest communication
        ingest_resp = task_client.post(
            "/api/v1/ingest/text",
            json={
                "project_id": "proj-villa",
                "source_type": "text",
                "content": "Architect will send the structural drawing by Friday.",
            },
        )
        comm_id = ingest_resp.json()["data"]["communication_id"]

        # Step 2: Pass explicit pre-computed upstream items
        action_id = "act-custom-001"
        action = ExtractedAction(
            action_id=action_id,
            action="Send structural drawing",
            evidence="Architect will send the structural drawing by Friday.",
            confidence=0.9,
        )
        resp_item = ResponsibilityAssignment(
            responsibility_id=str(uuid4()),
            action_id=action_id,
            responsible_party="Architect",
            responsibility_type="role",
            evidence="Architect will send",
            confidence=0.9,
        )
        dl_item = DeadlineAssignment(
            deadline_id=str(uuid4()),
            action_id=action_id,
            deadline="Friday",
            deadline_type="relative_day",
            normalized_deadline="2026-09-18",
            evidence="by Friday",
            confidence=0.9,
        )
        dec_item = ExtractedDecision(
            decision_id=str(uuid4()),
            description="Client approved structural layout",
            item_type="approval",
            status="approved",
            evidence="approved",
            confidence=0.9,
        )

        resp = task_client.post(
            "/api/v1/tasks/structure",
            json={
                "communication_id": comm_id,
                "actions": [action.model_dump(mode="json")],
                "responsibilities": [resp_item.model_dump(mode="json")],
                "deadlines": [dl_item.model_dump(mode="json")],
                "decisions": [dec_item.model_dump(mode="json")],
            },
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["task_count"] == 1
        t = data["tasks"][0]
        assert t["action_id"] == action_id
        assert t["title"] == "Send structural drawing"
        assert t["responsible_party"] == "Architect"
        assert t["responsibility_type"] == "role"
        assert t["deadline"] == "Friday"
        assert t["deadline_type"] == "relative_day"
        assert t["normalized_deadline"] == "2026-09-18"
        assert "approved" in t["decision_context"]

    def test_structure_tasks_communication_not_found_returns_404(self, task_client: TestClient) -> None:
        resp = task_client.post(
            "/api/v1/tasks/structure",
            json={"communication_id": "non-existent-comm-id"},
        )
        assert resp.status_code == 404
        body = resp.json()
        assert "not found" in body["detail"].lower()

    def test_structure_tasks_blank_communication_id_returns_422(self, task_client: TestClient) -> None:
        resp = task_client.post(
            "/api/v1/tasks/structure",
            json={"communication_id": "   "},
        )
        assert resp.status_code == 422

    def test_structure_tasks_empty_actions_returns_empty_tasks_200(self, task_client: TestClient) -> None:
        ingest_resp = task_client.post(
            "/api/v1/ingest/text",
            json={
                "project_id": "proj-villa",
                "source_type": "text",
                "content": "General status update: weather on site is clear today.",
            },
        )
        comm_id = ingest_resp.json()["data"]["communication_id"]

        resp = task_client.post(
            "/api/v1/tasks/structure",
            json={
                "communication_id": comm_id,
                "actions": [],
            },
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["tasks"] == []
        assert data["task_count"] == 0

    def test_structure_tasks_unknown_action_id_in_upstream_returns_422(self, task_client: TestClient) -> None:
        ingest_resp = task_client.post(
            "/api/v1/ingest/text",
            json={
                "project_id": "proj-villa",
                "source_type": "text",
                "content": "Architect will send drawing.",
            },
        )
        comm_id = ingest_resp.json()["data"]["communication_id"]

        action = ExtractedAction(action_id="act-1", action="Send drawing", evidence="Send drawing", confidence=0.9)
        bad_resp = ResponsibilityAssignment(
            responsibility_id=str(uuid4()),
            action_id="UNKNOWN_ACTION",
            responsible_party="Architect",
            responsibility_type="role",
            evidence="Architect",
            confidence=0.9,
        )

        resp = task_client.post(
            "/api/v1/tasks/structure",
            json={
                "communication_id": comm_id,
                "actions": [action.model_dump(mode="json")],
                "responsibilities": [bad_resp.model_dump(mode="json")],
            },
        )
        assert resp.status_code == 422
        body = resp.json()
        assert "unknown action_id" in body["detail"].lower()

    def test_structure_tasks_upstream_module_failure_returns_502(self, task_client: TestClient) -> None:
        ingest_resp = task_client.post(
            "/api/v1/ingest/text",
            json={
                "project_id": "proj-villa",
                "source_type": "text",
                "content": "Architect will send drawing.",
            },
        )
        comm_id = ingest_resp.json()["data"]["communication_id"]

        # Mock understanding service to fail
        def _failing_analyze(record: object) -> None:
            raise UnderstandingProviderError("Simulated LLM network error")

        original_analyze = tasks_mod._understanding_service.analyze
        tasks_mod._understanding_service.analyze = _failing_analyze  # type: ignore[assignment]

        try:
            resp = task_client.post(
                "/api/v1/tasks/structure",
                json={
                    "communication_id": comm_id,
                    "include_understanding_context": True,
                },
            )
            assert resp.status_code == 502
            body = resp.json()
            assert "understanding could not be generated" in body["detail"].lower()
        finally:
            tasks_mod._understanding_service.analyze = original_analyze  # type: ignore[assignment]

    def test_health_endpoint_includes_structured_tasks(self, task_client: TestClient) -> None:
        resp = task_client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert "structured_tasks" in body["modules"]
        expected_modules = [
            "ingestion",
            "understanding",
            "action_extraction",
            "responsibility",
            "deadline",
            "decision",
            "structured_tasks",
        ]
        assert body["modules"] == expected_modules
