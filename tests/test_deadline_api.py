"""
ArchScale — Module 5 Tests
Integration tests for the Deadline Detection API endpoint: POST /api/v1/deadlines/extract.
"""

from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

import app.api.action_extraction as action_mod
import app.api.deadline as deadline_mod
import app.api.ingestion as ingestion_mod
import app.api.responsibility as resp_mod
import app.api.understanding as understanding_mod
from app.llm.provider import FakeLLMProvider
from app.main import create_app
from app.services.action_extraction_service import ActionExtractionService
from app.services.deadline_service import DeadlineService
from app.services.ingestion_service import IngestionService
from app.services.responsibility_service import ResponsibilityService
from app.services.understanding_service import CommunicationUnderstandingService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def deadline_client(tmp_storage: dict[str, Path]) -> TestClient:
    """
    TestClient with:
      - Isolated IngestionService backed by tmp storage
      - FakeLLMProvider for understanding
      - FakeLLMProvider for action extraction
      - FakeLLMProvider for responsibility detection
      - FakeLLMProvider for deadline detection
    """
    isolated_ingestion = IngestionService(
        raw_path=tmp_storage["raw"],
        processed_path=tmp_storage["processed"],
    )
    fake_llm_und = FakeLLMProvider()
    fake_llm_act = FakeLLMProvider()
    fake_llm_resp = FakeLLMProvider()
    fake_llm_dl = FakeLLMProvider()

    isolated_und = CommunicationUnderstandingService(llm_provider=fake_llm_und)
    isolated_act = ActionExtractionService(llm_provider=fake_llm_act)
    isolated_resp = ResponsibilityService(llm_provider=fake_llm_resp)
    isolated_dl = DeadlineService(llm_provider=fake_llm_dl)

    app = create_app()

    # Save originals
    orig_ingest = ingestion_mod._service
    orig_und_ingest = understanding_mod._ingestion_service
    orig_und = understanding_mod._understanding_service
    orig_act_ingest = action_mod._ingestion_service
    orig_act_und = action_mod._understanding_service
    orig_act = action_mod._action_extraction_service
    orig_resp_ingest = resp_mod._ingestion_service
    orig_resp_und = resp_mod._understanding_service
    orig_resp_act = resp_mod._action_extraction_service
    orig_resp = resp_mod._responsibility_service
    orig_dl_ingest = deadline_mod._ingestion_service
    orig_dl_und = deadline_mod._understanding_service
    orig_dl_act = deadline_mod._action_extraction_service
    orig_dl_resp = deadline_mod._responsibility_service
    orig_dl = deadline_mod._deadline_service

    # Patch
    ingestion_mod._service = isolated_ingestion
    understanding_mod._ingestion_service = isolated_ingestion
    understanding_mod._understanding_service = isolated_und
    action_mod._ingestion_service = isolated_ingestion
    action_mod._understanding_service = isolated_und
    action_mod._action_extraction_service = isolated_act
    resp_mod._ingestion_service = isolated_ingestion
    resp_mod._understanding_service = isolated_und
    resp_mod._action_extraction_service = isolated_act
    resp_mod._responsibility_service = isolated_resp
    deadline_mod._ingestion_service = isolated_ingestion
    deadline_mod._understanding_service = isolated_und
    deadline_mod._action_extraction_service = isolated_act
    deadline_mod._responsibility_service = isolated_resp
    deadline_mod._deadline_service = isolated_dl

    with TestClient(app) as c:
        yield c

    # Restore
    ingestion_mod._service = orig_ingest
    understanding_mod._ingestion_service = orig_und_ingest
    understanding_mod._understanding_service = orig_und
    action_mod._ingestion_service = orig_act_ingest
    action_mod._understanding_service = orig_act_und
    action_mod._action_extraction_service = orig_act
    resp_mod._ingestion_service = orig_resp_ingest
    resp_mod._understanding_service = orig_resp_und
    resp_mod._action_extraction_service = orig_resp_act
    resp_mod._responsibility_service = orig_resp
    deadline_mod._ingestion_service = orig_dl_ingest
    deadline_mod._understanding_service = orig_dl_und
    deadline_mod._action_extraction_service = orig_dl_act
    deadline_mod._responsibility_service = orig_dl_resp
    deadline_mod._deadline_service = orig_dl


# ---------------------------------------------------------------------------
# Tests: POST /api/v1/deadlines/extract
# ---------------------------------------------------------------------------


class TestDeadlineEndpoint:
    def test_extract_deadlines_success(self, deadline_client: TestClient) -> None:
        # Step 1: Ingest text
        ingest_resp = deadline_client.post(
            "/api/v1/ingest/text",
            json={
                "project_id": "proj-villa",
                "content": "Architect will send the structural drawing by Friday.",
                "source_type": "text",
            },
        )
        assert ingest_resp.status_code == 201
        comm_id = ingest_resp.json()["data"]["communication_id"]

        # Step 2: Extract deadlines
        extract_resp = deadline_client.post(
            "/api/v1/deadlines/extract",
            json={
                "communication_id": comm_id,
                "include_context": True,
            },
        )
        assert extract_resp.status_code == 200
        body = extract_resp.json()
        assert body["success"] is True
        data = body["data"]
        assert data["communication_id"] == comm_id
        assert data["project_id"] == "proj-villa"
        assert len(data["assignments"]) > 0

        first_assign = data["assignments"][0]
        assert "deadline_id" in first_assign
        assert "action_id" in first_assign
        assert "deadline" in first_assign
        assert "deadline_type" in first_assign
        assert "confidence" in first_assign
        # Validate UUID4
        uuid_obj = UUID(first_assign["deadline_id"])
        assert uuid_obj.version == 4

    def test_extract_deadlines_without_context(self, deadline_client: TestClient) -> None:
        ingest_resp = deadline_client.post(
            "/api/v1/ingest/text",
            json={
                "project_id": "proj-villa",
                "content": "Contractor must verify the cabinet dimensions.",
                "source_type": "text",
            },
        )
        comm_id = ingest_resp.json()["data"]["communication_id"]

        extract_resp = deadline_client.post(
            "/api/v1/deadlines/extract",
            json={
                "communication_id": comm_id,
                "include_context": False,
            },
        )
        assert extract_resp.status_code == 200
        body = extract_resp.json()
        assert body["success"] is True
        assert len(body["data"]["assignments"]) > 0

    def test_extract_deadlines_with_explicit_actions(
        self, deadline_client: TestClient
    ) -> None:
        ingest_resp = deadline_client.post(
            "/api/v1/ingest/text",
            json={
                "project_id": "proj-villa",
                "content": "Acme Security will provide the report by Monday.",
                "source_type": "text",
            },
        )
        comm_id = ingest_resp.json()["data"]["communication_id"]

        custom_actions = [
            {
                "action_id": "act-explicit-999",
                "action": "Provide the report",
                "evidence": "Acme Security will provide the report by Monday.",
                "confidence": 0.95,
                "action_type": "deliverable",
            }
        ]

        extract_resp = deadline_client.post(
            "/api/v1/deadlines/extract",
            json={
                "communication_id": comm_id,
                "include_context": False,
                "actions": custom_actions,
            },
        )
        assert extract_resp.status_code == 200
        data = extract_resp.json()["data"]
        assert len(data["assignments"]) == 1
        assert data["assignments"][0]["action_id"] == "act-explicit-999"

    def test_communication_not_found(self, deadline_client: TestClient) -> None:
        resp = deadline_client.post(
            "/api/v1/deadlines/extract",
            json={"communication_id": "nonexistent-id"},
        )
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_blank_communication_id_fails_validation(
        self, deadline_client: TestClient
    ) -> None:
        resp = deadline_client.post(
            "/api/v1/deadlines/extract",
            json={"communication_id": "   "},
        )
        assert resp.status_code == 422

    def test_module2_failure_returns_502(self, deadline_client: TestClient) -> None:
        ingest_resp = deadline_client.post(
            "/api/v1/ingest/text",
            json={
                "project_id": "proj-villa",
                "content": "Some valid content.",
                "source_type": "text",
            },
        )
        comm_id = ingest_resp.json()["data"]["communication_id"]

        failing_und = CommunicationUnderstandingService(
            llm_provider=FakeLLMProvider(should_fail=True)
        )
        orig = deadline_mod._understanding_service
        deadline_mod._understanding_service = failing_und
        try:
            resp = deadline_client.post(
                "/api/v1/deadlines/extract",
                json={"communication_id": comm_id, "include_context": True},
            )
            assert resp.status_code == 502
            assert "understanding could not be generated" in resp.json()["detail"].lower()
        finally:
            deadline_mod._understanding_service = orig

    def test_module3_failure_returns_502(self, deadline_client: TestClient) -> None:
        ingest_resp = deadline_client.post(
            "/api/v1/ingest/text",
            json={
                "project_id": "proj-villa",
                "content": "Some valid content.",
                "source_type": "text",
            },
        )
        comm_id = ingest_resp.json()["data"]["communication_id"]

        failing_act = ActionExtractionService(
            llm_provider=FakeLLMProvider(should_fail=True)
        )
        orig = deadline_mod._action_extraction_service
        deadline_mod._action_extraction_service = failing_act
        try:
            resp = deadline_client.post(
                "/api/v1/deadlines/extract",
                json={"communication_id": comm_id},
            )
            assert resp.status_code == 502
            assert "action extraction failed" in resp.json()["detail"].lower()
        finally:
            deadline_mod._action_extraction_service = orig

    def test_module4_failure_returns_502(self, deadline_client: TestClient) -> None:
        ingest_resp = deadline_client.post(
            "/api/v1/ingest/text",
            json={
                "project_id": "proj-villa",
                "content": "Some valid content.",
                "source_type": "text",
            },
        )
        comm_id = ingest_resp.json()["data"]["communication_id"]

        failing_resp = ResponsibilityService(
            llm_provider=FakeLLMProvider(should_fail=True)
        )
        orig = deadline_mod._responsibility_service
        deadline_mod._responsibility_service = failing_resp
        try:
            resp = deadline_client.post(
                "/api/v1/deadlines/extract",
                json={"communication_id": comm_id, "include_context": True},
            )
            assert resp.status_code == 502
            assert "responsibility detection failed" in resp.json()["detail"].lower()
        finally:
            deadline_mod._responsibility_service = orig

    def test_schema_boundary_violation_returns_502(
        self, deadline_client: TestClient
    ) -> None:
        """Module 5 boundary: If LLM returns owner or decision, return controlled 502."""
        ingest_resp = deadline_client.post(
            "/api/v1/ingest/text",
            json={
                "project_id": "proj-villa",
                "content": "Architect will send drawing.",
                "source_type": "text",
            },
        )
        comm_id = ingest_resp.json()["data"]["communication_id"]

        dirty_llm = FakeLLMProvider(
            fixed_response={
                "assignments": [
                    {
                        "action_id": "act-1",
                        "deadline": "Friday",
                        "deadline_type": "relative_day",
                        "confidence": 0.9,
                        "owner": "Architect",
                    }
                ]
            }
        )
        orig = deadline_mod._deadline_service
        deadline_mod._deadline_service = DeadlineService(llm_provider=dirty_llm)
        try:
            resp = deadline_client.post(
                "/api/v1/deadlines/extract",
                json={
                    "communication_id": comm_id,
                    "actions": [
                        {
                            "action_id": "act-1",
                            "action": "Send drawing",
                            "evidence": "Architect will send drawing.",
                            "confidence": 0.9,
                            "action_type": "deliverable",
                        }
                    ],
                },
            )
            assert resp.status_code == 502
            assert "violated schema boundaries" in resp.json()["detail"].lower()
        finally:
            deadline_mod._deadline_service = orig

    def test_health_check_updated(self, deadline_client: TestClient) -> None:
        resp = deadline_client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "deadline" in data["modules"]
