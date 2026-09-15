"""
ArchScale — Module 3 Tests
Integration tests for the Action Extraction API endpoint: POST /api/v1/actions/extract.
"""

from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

import app.api.action_extraction as action_mod
import app.api.ingestion as ingestion_mod
import app.api.understanding as understanding_mod
from app.llm.provider import FakeLLMProvider
from app.main import create_app
from app.services.action_extraction_service import ActionExtractionService
from app.services.ingestion_service import IngestionService
from app.services.understanding_service import CommunicationUnderstandingService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def action_client(tmp_storage: dict[str, Path]) -> TestClient:
    """
    TestClient with:
      - Isolated IngestionService backed by tmp storage
      - FakeLLMProvider for understanding
      - FakeLLMProvider for action extraction
    """
    isolated_ingestion = IngestionService(
        raw_path=tmp_storage["raw"],
        processed_path=tmp_storage["processed"],
    )
    fake_llm_understanding = FakeLLMProvider()
    fake_llm_actions = FakeLLMProvider()

    isolated_understanding = CommunicationUnderstandingService(llm_provider=fake_llm_understanding)
    isolated_action = ActionExtractionService(llm_provider=fake_llm_actions)

    app = create_app()

    # Save originals
    orig_ingest = ingestion_mod._service
    orig_und_ingest = understanding_mod._ingestion_service
    orig_und = understanding_mod._understanding_service
    orig_act_ingest = action_mod._ingestion_service
    orig_act_und = action_mod._understanding_service
    orig_act = action_mod._action_extraction_service

    # Patch
    ingestion_mod._service = isolated_ingestion
    understanding_mod._ingestion_service = isolated_ingestion
    understanding_mod._understanding_service = isolated_understanding
    action_mod._ingestion_service = isolated_ingestion
    action_mod._understanding_service = isolated_understanding
    action_mod._action_extraction_service = isolated_action

    with TestClient(app) as c:
        yield c

    # Restore
    ingestion_mod._service = orig_ingest
    understanding_mod._ingestion_service = orig_und_ingest
    understanding_mod._understanding_service = orig_und
    action_mod._ingestion_service = orig_act_ingest
    action_mod._understanding_service = orig_act_und
    action_mod._action_extraction_service = orig_act


# ---------------------------------------------------------------------------
# Tests: POST /api/v1/actions/extract
# ---------------------------------------------------------------------------


class TestActionExtractionEndpoint:
    def test_extract_actions_success(self, action_client: TestClient) -> None:
        # Step 1: Ingest text
        ingest_resp = action_client.post(
            "/api/v1/ingest/text",
            json={
                "project_id": "proj-villa",
                "text": "Architect will send the structural drawing by Friday.",
                "source_type": "text",
            },
        )
        assert ingest_resp.status_code == 201
        comm_id = ingest_resp.json()["data"]["communication_id"]

        # Step 2: Extract actions
        extract_resp = action_client.post(
            "/api/v1/actions/extract",
            json={"communication_id": comm_id},
        )
        assert extract_resp.status_code == 200
        body = extract_resp.json()
        assert body["success"] is True
        data = body["data"]

        assert data["project_id"] == "proj-villa"
        assert data["communication_id"] == comm_id
        assert len(data["actions"]) > 0

        for action in data["actions"]:
            assert "action_id" in action
            # Verify UUID format
            UUID(action["action_id"])
            assert "action" in action
            assert "evidence" in action
            assert "confidence" in action
            assert 0.0 <= action["confidence"] <= 1.0
            assert "action_type" in action

            # Strict negative boundary: NO owner, deadline, decision
            assert "owner" not in action
            assert "responsible_person" not in action
            assert "deadline" not in action
            assert "due_date" not in action
            assert "decision" not in action
            assert "approval" not in action

    def test_extract_actions_404_for_unknown_communication(self, action_client: TestClient) -> None:
        resp = action_client.post(
            "/api/v1/actions/extract",
            json={"communication_id": "nonexistent-id-999"},
        )
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_extract_actions_422_for_missing_fields(self, action_client: TestClient) -> None:
        resp = action_client.post(
            "/api/v1/actions/extract",
            json={},
        )
        assert resp.status_code == 422

    def test_extract_actions_422_for_blank_communication_id(self, action_client: TestClient) -> None:
        resp = action_client.post(
            "/api/v1/actions/extract",
            json={"communication_id": "   "},
        )
        assert resp.status_code == 422

    def test_extract_actions_controlled_error_when_module_2_fails(
        self, action_client: TestClient
    ) -> None:
        """Requirement: Do not silently fall back to raw content when Module 2 is unavailable. Return a controlled error."""
        # Ingest text
        ingest_resp = action_client.post(
            "/api/v1/ingest/text",
            json={
                "project_id": "proj-villa",
                "text": "Contractor will verify the site measurements.",
                "source_type": "text",
            },
        )
        comm_id = ingest_resp.json()["data"]["communication_id"]

        # Make Module 2 understanding fail
        failing_llm = FakeLLMProvider(should_fail=True)
        action_mod._understanding_service = CommunicationUnderstandingService(llm_provider=failing_llm)

        resp = action_client.post(
            "/api/v1/actions/extract",
            json={"communication_id": comm_id},
        )
        assert resp.status_code == 502
        assert "Module 2 understanding could not be generated" in resp.json()["detail"]

    def test_extract_actions_502_when_action_llm_fails(self, action_client: TestClient) -> None:
        # Ingest text
        ingest_resp = action_client.post(
            "/api/v1/ingest/text",
            json={
                "project_id": "proj-villa",
                "text": "Contractor will verify the site measurements.",
                "source_type": "text",
            },
        )
        comm_id = ingest_resp.json()["data"]["communication_id"]

        # Make action service fail
        failing_llm = FakeLLMProvider(should_fail=True)
        action_mod._action_extraction_service = ActionExtractionService(llm_provider=failing_llm)

        resp = action_client.post(
            "/api/v1/actions/extract",
            json={"communication_id": comm_id},
        )
        assert resp.status_code == 502
        assert "unavailable" in resp.json()["detail"].lower()

    def test_extract_actions_502_when_action_llm_returns_invalid_json(
        self, action_client: TestClient
    ) -> None:
        # Ingest text
        ingest_resp = action_client.post(
            "/api/v1/ingest/text",
            json={
                "project_id": "proj-villa",
                "text": "Contractor will verify the site measurements.",
                "source_type": "text",
            },
        )
        comm_id = ingest_resp.json()["data"]["communication_id"]

        bad_json_llm = FakeLLMProvider(bad_json=True)
        action_mod._action_extraction_service = ActionExtractionService(llm_provider=bad_json_llm)

        resp = action_client.post(
            "/api/v1/actions/extract",
            json={"communication_id": comm_id},
        )
        assert resp.status_code == 502
        assert "could not be validated" in resp.json()["detail"].lower()

    def test_health_endpoint_includes_action_extraction(self, action_client: TestClient) -> None:
        resp = action_client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "action_extraction" in data["modules"]
        assert data["version"] == "2.0.0"
