"""
ArchScale — Module 6 Tests
Integration tests for the Decision & Approval Extraction API endpoint: POST /api/v1/decisions/extract.
"""

from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

import app.api.decision as decision_mod
import app.api.ingestion as ingestion_mod
import app.api.understanding as understanding_mod
from app.llm.provider import FakeLLMProvider
from app.main import create_app
from app.services.decision_service import DecisionService
from app.services.ingestion_service import IngestionService
from app.services.understanding_service import CommunicationUnderstandingService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def decision_client(tmp_storage: dict[str, Path]) -> TestClient:
    """
    TestClient with:
      - Isolated IngestionService backed by tmp storage
      - FakeLLMProvider for understanding
      - FakeLLMProvider for decision extraction
    """
    isolated_ingestion = IngestionService(
        raw_path=tmp_storage["raw"],
        processed_path=tmp_storage["processed"],
    )
    fake_llm_und = FakeLLMProvider()
    fake_llm_dec = FakeLLMProvider()

    isolated_und = CommunicationUnderstandingService(llm_provider=fake_llm_und)
    isolated_dec = DecisionService(llm_provider=fake_llm_dec)

    app = create_app()

    # Save originals
    orig_ingest = ingestion_mod._service
    orig_und_ingest = understanding_mod._ingestion_service
    orig_und = understanding_mod._understanding_service
    orig_dec_ingest = decision_mod._ingestion_service
    orig_dec_und = decision_mod._understanding_service
    orig_dec = decision_mod._decision_service

    # Patch
    ingestion_mod._service = isolated_ingestion
    understanding_mod._ingestion_service = isolated_ingestion
    understanding_mod._understanding_service = isolated_und
    decision_mod._ingestion_service = isolated_ingestion
    decision_mod._understanding_service = isolated_und
    decision_mod._decision_service = isolated_dec

    with TestClient(app) as c:
        yield c

    # Restore
    ingestion_mod._service = orig_ingest
    understanding_mod._ingestion_service = orig_und_ingest
    understanding_mod._understanding_service = orig_und
    decision_mod._ingestion_service = orig_dec_ingest
    decision_mod._understanding_service = orig_dec_und
    decision_mod._decision_service = orig_dec


# ---------------------------------------------------------------------------
# Tests: POST /api/v1/decisions/extract
# ---------------------------------------------------------------------------


class TestDecisionEndpoint:
    def test_extract_decisions_success(self, decision_client: TestClient) -> None:
        # Step 1: Ingest text
        ingest_resp = decision_client.post(
            "/api/v1/ingest/text",
            json={
                "project_id": "proj-villa",
                "content": "Client approved the revised kitchen layout. We decided to use granite for the counter.",
                "source_type": "text",
            },
        )
        assert ingest_resp.status_code == 201
        comm_id = ingest_resp.json()["data"]["communication_id"]

        # Step 2: Extract decisions
        extract_resp = decision_client.post(
            "/api/v1/decisions/extract",
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
        assert len(data["decisions"]) > 0

        first_item = data["decisions"][0]
        assert "decision_id" in first_item
        assert "item_type" in first_item
        assert "description" in first_item
        assert "status" in first_item
        assert "evidence" in first_item
        assert "confidence" in first_item

        # Validate UUID4
        uuid_obj = UUID(first_item["decision_id"])
        assert uuid_obj.version == 4

    def test_extract_decisions_without_understanding_context(
        self, decision_client: TestClient
    ) -> None:
        ingest_resp = decision_client.post(
            "/api/v1/ingest/text",
            json={
                "project_id": "proj-villa",
                "content": "Client approved the revised kitchen layout.",
                "source_type": "text",
            },
        )
        comm_id = ingest_resp.json()["data"]["communication_id"]

        extract_resp = decision_client.post(
            "/api/v1/decisions/extract",
            json={
                "communication_id": comm_id,
                "include_understanding_context": False,
            },
        )
        assert extract_resp.status_code == 200
        body = extract_resp.json()
        assert body["success"] is True
        assert len(body["data"]["decisions"]) > 0

    def test_communication_not_found(self, decision_client: TestClient) -> None:
        resp = decision_client.post(
            "/api/v1/decisions/extract",
            json={"communication_id": "nonexistent-id"},
        )
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_blank_communication_id_fails_validation(
        self, decision_client: TestClient
    ) -> None:
        resp = decision_client.post(
            "/api/v1/decisions/extract",
            json={"communication_id": "   "},
        )
        assert resp.status_code == 422

    def test_module2_failure_returns_502(self, decision_client: TestClient) -> None:
        ingest_resp = decision_client.post(
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
        orig = decision_mod._understanding_service
        decision_mod._understanding_service = failing_und
        try:
            resp = decision_client.post(
                "/api/v1/decisions/extract",
                json={"communication_id": comm_id, "include_understanding_context": True},
            )
            assert resp.status_code == 502
            assert "understanding could not be generated" in resp.json()["detail"].lower()
        finally:
            decision_mod._understanding_service = orig

    def test_schema_boundary_violation_returns_502(
        self, decision_client: TestClient
    ) -> None:
        """Module 6 boundary: If LLM returns owner/deadline, return controlled 502."""
        ingest_resp = decision_client.post(
            "/api/v1/ingest/text",
            json={
                "project_id": "proj-villa",
                "content": "We decided to use granite.",
                "source_type": "text",
            },
        )
        comm_id = ingest_resp.json()["data"]["communication_id"]

        dirty_llm = FakeLLMProvider(
            fixed_response={
                "decisions": [
                    {
                        "item_type": "decision",
                        "description": "Use granite",
                        "status": "decided",
                        "evidence": "We decided to use granite.",
                        "confidence": 0.95,
                        "owner": "Architect",
                        "deadline": "Friday",
                    }
                ]
            }
        )
        orig = decision_mod._decision_service
        decision_mod._decision_service = DecisionService(llm_provider=dirty_llm)
        try:
            resp = decision_client.post(
                "/api/v1/decisions/extract",
                json={"communication_id": comm_id},
            )
            assert resp.status_code == 502
            assert "violated schema boundaries" in resp.json()["detail"].lower()
        finally:
            decision_mod._decision_service = orig

    def test_llm_provider_failure_returns_502(
        self, decision_client: TestClient
    ) -> None:
        ingest_resp = decision_client.post(
            "/api/v1/ingest/text",
            json={
                "project_id": "proj-villa",
                "content": "We decided to use granite.",
                "source_type": "text",
            },
        )
        comm_id = ingest_resp.json()["data"]["communication_id"]

        failing_dec = DecisionService(llm_provider=FakeLLMProvider(should_fail=True))
        orig = decision_mod._decision_service
        decision_mod._decision_service = failing_dec
        try:
            resp = decision_client.post(
                "/api/v1/decisions/extract",
                json={"communication_id": comm_id},
            )
            assert resp.status_code == 502
            assert "unavailable" in resp.json()["detail"].lower()
        finally:
            decision_mod._decision_service = orig

    def test_health_check_updated(self, decision_client: TestClient) -> None:
        resp = decision_client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "decision" in data["modules"]
