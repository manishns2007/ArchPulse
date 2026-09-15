"""
ArchScale — Module 2 Tests
Tests for the understanding API endpoint (HTTP layer).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.understanding import (
    get_ingestion_service,
    get_understanding_service,
)
from app.llm.provider import FakeLLMProvider, _default_fake_response
from app.main import create_app
from app.models.communication import CommunicationRecord, IngestionStatus, SourceType
from app.models.understanding import VALID_COMMUNICATION_TYPES
from app.services.ingestion_service import IngestionService
from app.services.understanding_service import CommunicationUnderstandingService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def understanding_client(tmp_storage: dict[str, Path]) -> TestClient:
    """
    TestClient with:
      - Isolated IngestionService backed by tmp storage (no real disk pollution)
      - FakeLLMProvider so no external API calls are made
    """
    isolated_ingestion = IngestionService(
        raw_path=tmp_storage["raw"],
        processed_path=tmp_storage["processed"],
    )
    fake_llm = FakeLLMProvider()
    isolated_understanding = CommunicationUnderstandingService(llm_provider=fake_llm)

    app = create_app()

    # Override Module 1 ingestion module's _service
    import app.api.ingestion as ingestion_mod
    import app.api.understanding as understanding_mod

    orig_ingest = ingestion_mod._service
    orig_understand_ingest = understanding_mod._ingestion_service
    orig_understand = understanding_mod._understanding_service

    ingestion_mod._service = isolated_ingestion
    understanding_mod._ingestion_service = isolated_ingestion
    understanding_mod._understanding_service = isolated_understanding

    with TestClient(app) as c:
        yield c

    # Restore originals
    ingestion_mod._service = orig_ingest
    understanding_mod._ingestion_service = orig_understand_ingest
    understanding_mod._understanding_service = orig_understand


@pytest.fixture()
def ingested_communication_id(understanding_client: TestClient) -> str:
    """Ingest a sample communication and return its communication_id."""
    resp = understanding_client.post(
        "/api/v1/ingest/text",
        json={
            "project_id": "proj-villa",
            "content": (
                "Client approved the revised kitchen layout. "
                "The architect noted the structural drawing needs updating. "
                "Contractor raised concerns about cabinet dimensions."
            ),
            "source_type": "text",
        },
    )
    assert resp.status_code == 201
    return resp.json()["data"]["communication_id"]


# ---------------------------------------------------------------------------
# POST /api/v1/understanding/analyze — successful analysis
# ---------------------------------------------------------------------------


class TestUnderstandingAPISuccess:
    def test_successful_analysis(
        self, understanding_client: TestClient, ingested_communication_id: str
    ) -> None:
        resp = understanding_client.post(
            "/api/v1/understanding/analyze",
            json={"communication_id": ingested_communication_id},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        data = body["data"]
        assert data["communication_id"] == ingested_communication_id
        assert data["project_id"] == "proj-villa"

    def test_response_contains_all_required_fields(
        self, understanding_client: TestClient, ingested_communication_id: str
    ) -> None:
        resp = understanding_client.post(
            "/api/v1/understanding/analyze",
            json={"communication_id": ingested_communication_id},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        for field in [
            "concise_summary",
            "detailed_summary",
            "topics",
            "stakeholders",
            "communication_type",
            "important_context",
            "project_id",
            "communication_id",
        ]:
            assert field in data, f"Missing field: {field}"

    def test_communication_type_is_valid(
        self, understanding_client: TestClient, ingested_communication_id: str
    ) -> None:
        resp = understanding_client.post(
            "/api/v1/understanding/analyze",
            json={"communication_id": ingested_communication_id},
        )
        assert resp.status_code == 200
        ct = resp.json()["data"]["communication_type"]
        assert ct in VALID_COMMUNICATION_TYPES

    def test_topics_is_list(
        self, understanding_client: TestClient, ingested_communication_id: str
    ) -> None:
        resp = understanding_client.post(
            "/api/v1/understanding/analyze",
            json={"communication_id": ingested_communication_id},
        )
        assert resp.status_code == 200
        assert isinstance(resp.json()["data"]["topics"], list)

    def test_stakeholders_is_list(
        self, understanding_client: TestClient, ingested_communication_id: str
    ) -> None:
        resp = understanding_client.post(
            "/api/v1/understanding/analyze",
            json={"communication_id": ingested_communication_id},
        )
        assert resp.status_code == 200
        assert isinstance(resp.json()["data"]["stakeholders"], list)

    def test_traceability_ids_match_source(
        self, understanding_client: TestClient, ingested_communication_id: str
    ) -> None:
        resp = understanding_client.post(
            "/api/v1/understanding/analyze",
            json={"communication_id": ingested_communication_id},
        )
        data = resp.json()["data"]
        assert data["communication_id"] == ingested_communication_id
        assert data["project_id"] == "proj-villa"

    def test_no_task_or_deadline_fields_in_response(
        self, understanding_client: TestClient, ingested_communication_id: str
    ) -> None:
        """Module 2 must NOT return task/deadline/responsibility/decision fields."""
        resp = understanding_client.post(
            "/api/v1/understanding/analyze",
            json={"communication_id": ingested_communication_id},
        )
        data = resp.json()["data"]
        forbidden_fields = {
            "tasks", "deadlines", "responsibilities", "decisions",
            "approvals", "action_items", "owners", "due_dates",
        }
        for field in forbidden_fields:
            assert field not in data, f"Forbidden field found in response: {field}"


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestUnderstandingAPIErrors:
    def test_unknown_communication_id_returns_404(
        self, understanding_client: TestClient
    ) -> None:
        resp = understanding_client.post(
            "/api/v1/understanding/analyze",
            json={"communication_id": "00000000-0000-0000-0000-000000000000"},
        )
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_missing_communication_id_returns_422(
        self, understanding_client: TestClient
    ) -> None:
        resp = understanding_client.post("/api/v1/understanding/analyze", json={})
        assert resp.status_code == 422

    def test_blank_communication_id_returns_422(
        self, understanding_client: TestClient
    ) -> None:
        resp = understanding_client.post(
            "/api/v1/understanding/analyze",
            json={"communication_id": "   "},
        )
        assert resp.status_code == 422

    def test_provider_failure_returns_502(
        self, tmp_storage: dict[str, Path]
    ) -> None:
        """A failing LLM provider should surface as HTTP 502."""
        isolated_ingestion = IngestionService(
            raw_path=tmp_storage["raw"],
            processed_path=tmp_storage["processed"],
        )
        failing_provider = FakeLLMProvider(should_fail=True)
        failing_understanding = CommunicationUnderstandingService(
            llm_provider=failing_provider
        )

        app = create_app()
        import app.api.ingestion as ingestion_mod
        import app.api.understanding as understanding_mod

        orig_ingest = ingestion_mod._service
        orig_understand_ingest = understanding_mod._ingestion_service
        orig_understand = understanding_mod._understanding_service

        ingestion_mod._service = isolated_ingestion
        understanding_mod._ingestion_service = isolated_ingestion
        understanding_mod._understanding_service = failing_understanding

        with TestClient(app) as client:
            # First ingest
            ingest_resp = client.post(
                "/api/v1/ingest/text",
                json={"project_id": "p", "content": "test content", "source_type": "text"},
            )
            comm_id = ingest_resp.json()["data"]["communication_id"]

            # Now analyze — should get 502
            analyze_resp = client.post(
                "/api/v1/understanding/analyze",
                json={"communication_id": comm_id},
            )
            assert analyze_resp.status_code == 502

        ingestion_mod._service = orig_ingest
        understanding_mod._ingestion_service = orig_understand_ingest
        understanding_mod._understanding_service = orig_understand

    def test_bad_json_response_returns_502(
        self, tmp_storage: dict[str, Path]
    ) -> None:
        """A malformed LLM JSON response should surface as HTTP 502."""
        isolated_ingestion = IngestionService(
            raw_path=tmp_storage["raw"],
            processed_path=tmp_storage["processed"],
        )
        bad_json_provider = FakeLLMProvider(bad_json=True)
        bad_json_understanding = CommunicationUnderstandingService(
            llm_provider=bad_json_provider
        )

        app = create_app()
        import app.api.ingestion as ingestion_mod
        import app.api.understanding as understanding_mod

        orig_ingest = ingestion_mod._service
        orig_understand_ingest = understanding_mod._ingestion_service
        orig_understand = understanding_mod._understanding_service

        ingestion_mod._service = isolated_ingestion
        understanding_mod._ingestion_service = isolated_ingestion
        understanding_mod._understanding_service = bad_json_understanding

        with TestClient(app) as client:
            ingest_resp = client.post(
                "/api/v1/ingest/text",
                json={"project_id": "p", "content": "test content", "source_type": "text"},
            )
            comm_id = ingest_resp.json()["data"]["communication_id"]

            analyze_resp = client.post(
                "/api/v1/understanding/analyze",
                json={"communication_id": comm_id},
            )
            assert analyze_resp.status_code == 502

        ingestion_mod._service = orig_ingest
        understanding_mod._ingestion_service = orig_understand_ingest
        understanding_mod._understanding_service = orig_understand


# ---------------------------------------------------------------------------
# Regression: Module 1 endpoints must still work
# ---------------------------------------------------------------------------


class TestModule1Regression:
    def test_ingest_text_still_works(self, understanding_client: TestClient) -> None:
        resp = understanding_client.post(
            "/api/v1/ingest/text",
            json={"project_id": "proj-reg", "content": "regression test", "source_type": "text"},
        )
        assert resp.status_code == 201

    def test_retrieve_by_id_still_works(self, understanding_client: TestClient) -> None:
        post_resp = understanding_client.post(
            "/api/v1/ingest/text",
            json={"project_id": "proj-reg", "content": "retrieve test", "source_type": "text"},
        )
        comm_id = post_resp.json()["data"]["communication_id"]
        get_resp = understanding_client.get(f"/api/v1/ingest/{comm_id}")
        assert get_resp.status_code == 200

    def test_health_endpoint_still_works(self, understanding_client: TestClient) -> None:
        resp = understanding_client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
