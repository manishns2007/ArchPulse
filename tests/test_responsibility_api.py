"""
ArchScale — Module 4 Tests
Integration tests for the Responsibility Detection API endpoint: POST /api/v1/responsibilities/extract.
"""

from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

import app.api.action_extraction as action_mod
import app.api.ingestion as ingestion_mod
import app.api.responsibility as resp_mod
import app.api.understanding as understanding_mod
from app.llm.provider import FakeLLMProvider
from app.main import create_app
from app.models.action_extraction import ExtractedAction
from app.services.action_extraction_service import ActionExtractionService
from app.services.ingestion_service import IngestionService
from app.services.responsibility_service import ResponsibilityService
from app.services.understanding_service import CommunicationUnderstandingService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def responsibility_client(tmp_storage: dict[str, Path]) -> TestClient:
    """
    TestClient with:
      - Isolated IngestionService backed by tmp storage
      - FakeLLMProvider for understanding
      - FakeLLMProvider for action extraction
      - FakeLLMProvider for responsibility detection
    """
    isolated_ingestion = IngestionService(
        raw_path=tmp_storage["raw"],
        processed_path=tmp_storage["processed"],
    )
    fake_llm_understanding = FakeLLMProvider()
    fake_llm_actions = FakeLLMProvider()
    fake_llm_resp = FakeLLMProvider()

    isolated_understanding = CommunicationUnderstandingService(llm_provider=fake_llm_understanding)
    isolated_action = ActionExtractionService(llm_provider=fake_llm_actions)
    isolated_resp = ResponsibilityService(llm_provider=fake_llm_resp)

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

    # Patch
    ingestion_mod._service = isolated_ingestion
    understanding_mod._ingestion_service = isolated_ingestion
    understanding_mod._understanding_service = isolated_understanding
    action_mod._ingestion_service = isolated_ingestion
    action_mod._understanding_service = isolated_understanding
    action_mod._action_extraction_service = isolated_action
    resp_mod._ingestion_service = isolated_ingestion
    resp_mod._understanding_service = isolated_understanding
    resp_mod._action_extraction_service = isolated_action
    resp_mod._responsibility_service = isolated_resp

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


# ---------------------------------------------------------------------------
# Tests: POST /api/v1/responsibilities/extract
# ---------------------------------------------------------------------------


class TestResponsibilityEndpoint:
    def test_extract_responsibilities_success(self, responsibility_client: TestClient) -> None:
        # Step 1: Ingest text
        ingest_resp = responsibility_client.post(
            "/api/v1/ingest/text",
            json={
                "project_id": "proj-villa",
                "content": "Architect will send the structural drawing by Friday.",
                "source_type": "text",
            },
        )
        assert ingest_resp.status_code == 201
        comm_id = ingest_resp.json()["data"]["communication_id"]

        # Step 2: Extract responsibilities
        extract_resp = responsibility_client.post(
            "/api/v1/responsibilities/extract",
            json={
                "communication_id": comm_id,
                "include_understanding_context": True,
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
        assert "responsibility_id" in first_assign
        assert "action_id" in first_assign
        assert "responsible_party" in first_assign
        assert "responsibility_type" in first_assign
        assert "confidence" in first_assign
        assert "evidence" in first_assign
        # Validate UUID4
        uuid_obj = UUID(first_assign["responsibility_id"])
        assert uuid_obj.version == 4

    def test_extract_responsibilities_without_understanding_context(
        self, responsibility_client: TestClient
    ) -> None:
        ingest_resp = responsibility_client.post(
            "/api/v1/ingest/text",
            json={
                "project_id": "proj-villa",
                "content": "Contractor must verify the cabinet dimensions.",
                "source_type": "text",
            },
        )
        comm_id = ingest_resp.json()["data"]["communication_id"]

        extract_resp = responsibility_client.post(
            "/api/v1/responsibilities/extract",
            json={
                "communication_id": comm_id,
                "include_understanding_context": False,
            },
        )
        assert extract_resp.status_code == 200
        body = extract_resp.json()
        assert body["success"] is True
        assert len(body["data"]["assignments"]) > 0

    def test_extract_responsibilities_with_explicit_actions(
        self, responsibility_client: TestClient
    ) -> None:
        ingest_resp = responsibility_client.post(
            "/api/v1/ingest/text",
            json={
                "project_id": "proj-villa",
                "content": "Acme Security will provide the penetration test report.",
                "source_type": "text",
            },
        )
        comm_id = ingest_resp.json()["data"]["communication_id"]

        custom_actions = [
            {
                "action_id": "action-custom-123",
                "action": "Provide penetration test report",
                "evidence": "Acme Security will provide the penetration test report.",
                "confidence": 0.95,
                "action_type": "deliverable",
            }
        ]

        extract_resp = responsibility_client.post(
            "/api/v1/responsibilities/extract",
            json={
                "communication_id": comm_id,
                "include_understanding_context": False,
                "actions": custom_actions,
            },
        )
        assert extract_resp.status_code == 200
        data = extract_resp.json()["data"]
        assert len(data["assignments"]) == 1
        assert data["assignments"][0]["action_id"] == "action-custom-123"

    def test_communication_not_found(self, responsibility_client: TestClient) -> None:
        resp = responsibility_client.post(
            "/api/v1/responsibilities/extract",
            json={"communication_id": "nonexistent-id"},
        )
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_blank_communication_id_fails_validation(
        self, responsibility_client: TestClient
    ) -> None:
        resp = responsibility_client.post(
            "/api/v1/responsibilities/extract",
            json={"communication_id": "   "},
        )
        assert resp.status_code == 422

    def test_module2_failure_returns_502(self, responsibility_client: TestClient) -> None:
        ingest_resp = responsibility_client.post(
            "/api/v1/ingest/text",
            json={
                "project_id": "proj-villa",
                "content": "Some valid content.",
                "source_type": "text",
            },
        )
        comm_id = ingest_resp.json()["data"]["communication_id"]

        # Patch Module 2 to simulate provider failure
        failing_und = CommunicationUnderstandingService(
            llm_provider=FakeLLMProvider(should_fail=True)
        )
        orig = resp_mod._understanding_service
        resp_mod._understanding_service = failing_und
        try:
            resp = responsibility_client.post(
                "/api/v1/responsibilities/extract",
                json={"communication_id": comm_id, "include_understanding_context": True},
            )
            assert resp.status_code == 502
            assert "understanding could not be generated" in resp.json()["detail"].lower()
        finally:
            resp_mod._understanding_service = orig

    def test_module3_failure_returns_502(self, responsibility_client: TestClient) -> None:
        ingest_resp = responsibility_client.post(
            "/api/v1/ingest/text",
            json={
                "project_id": "proj-villa",
                "content": "Some valid content.",
                "source_type": "text",
            },
        )
        comm_id = ingest_resp.json()["data"]["communication_id"]

        # Patch Module 3 to simulate provider failure
        failing_act = ActionExtractionService(
            llm_provider=FakeLLMProvider(should_fail=True)
        )
        orig = resp_mod._action_extraction_service
        resp_mod._action_extraction_service = failing_act
        try:
            resp = responsibility_client.post(
                "/api/v1/responsibilities/extract",
                json={"communication_id": comm_id},
            )
            assert resp.status_code == 502
            assert "action extraction failed" in resp.json()["detail"].lower()
        finally:
            resp_mod._action_extraction_service = orig

    def test_schema_boundary_violation_returns_502(
        self, responsibility_client: TestClient
    ) -> None:
        """Module 4 boundary: If LLM injects deadline/decision, return controlled 502."""
        ingest_resp = responsibility_client.post(
            "/api/v1/ingest/text",
            json={
                "project_id": "proj-villa",
                "content": "Architect will send drawing.",
                "source_type": "text",
            },
        )
        comm_id = ingest_resp.json()["data"]["communication_id"]

        # LLM returns deadline
        dirty_llm = FakeLLMProvider(
            fixed_response={
                "assignments": [
                    {
                        "action_id": "act-1",
                        "responsible_party": "Architect",
                        "responsibility_type": "role",
                        "evidence": "Architect will send drawing.",
                        "confidence": 0.9,
                        "deadline": "Friday",
                    }
                ]
            }
        )
        orig = resp_mod._responsibility_service
        resp_mod._responsibility_service = ResponsibilityService(llm_provider=dirty_llm)
        try:
            resp = responsibility_client.post(
                "/api/v1/responsibilities/extract",
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
            resp_mod._responsibility_service = orig

    def test_health_check_updated(self, responsibility_client: TestClient) -> None:
        resp = responsibility_client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "responsibility" in data["modules"]
