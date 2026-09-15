"""
ArchScale — Module 1 Tests
Tests for the ingestion API endpoints (HTTP layer).
"""

from __future__ import annotations

import io
import json

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# POST /api/v1/ingest/text — Text ingestion
# ---------------------------------------------------------------------------


class TestTextIngestion:
    def test_valid_text_ingestion(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/ingest/text",
            json={
                "project_id": "proj-001",
                "content": "We discussed the bridge design today.",
                "source_type": "text",
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["success"] is True
        data = body["data"]
        assert data["project_id"] == "proj-001"
        assert data["source_type"] == "text"
        assert data["status"] == "ingested"
        assert "communication_id" in data
        assert "timestamp" in data
        assert data["raw_content"] == "We discussed the bridge design today."
        assert data["metadata"]["char_count"] > 0
        assert data["storage_path"] is None  # text has no file

    def test_transcript_ingestion(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/ingest/text",
            json={
                "project_id": "proj-002",
                "content": "Alice: The deadline is Friday.\nBob: Confirmed.",
                "source_type": "transcript",
            },
        )
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["source_type"] == "transcript"
        assert "Alice" in data["raw_content"]

    def test_empty_content_rejected(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/ingest/text",
            json={"project_id": "proj-001", "content": "", "source_type": "text"},
        )
        assert resp.status_code == 422  # Pydantic min_length=1

    def test_whitespace_only_content_rejected(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/ingest/text",
            json={"project_id": "proj-001", "content": "   \n\t  ", "source_type": "text"},
        )
        assert resp.status_code in (400, 422)

    def test_missing_project_id_rejected(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/ingest/text",
            json={"content": "Some text", "source_type": "text"},
        )
        assert resp.status_code == 422

    def test_blank_project_id_rejected(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/ingest/text",
            json={"project_id": "   ", "content": "Some text", "source_type": "text"},
        )
        assert resp.status_code in (400, 422)

    def test_invalid_source_type_for_text_rejected(self, client: TestClient) -> None:
        """source_type='pdf_file' is not valid for the text endpoint."""
        resp = client.post(
            "/api/v1/ingest/text",
            json={"project_id": "proj-001", "content": "hello", "source_type": "pdf_file"},
        )
        assert resp.status_code in (400, 422)

    def test_content_is_trimmed(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/ingest/text",
            json={
                "project_id": "proj-001",
                "content": "  trimmed content  ",
                "source_type": "text",
            },
        )
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["raw_content"] == "trimmed content"

    def test_generated_communication_id_is_uuid(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/ingest/text",
            json={"project_id": "proj-001", "content": "hello world", "source_type": "text"},
        )
        assert resp.status_code == 201
        comm_id = resp.json()["data"]["communication_id"]
        # UUID format: 8-4-4-4-12 hex chars
        import re
        assert re.match(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
            comm_id,
        )


# ---------------------------------------------------------------------------
# POST /api/v1/ingest/file — File ingestion
# ---------------------------------------------------------------------------


class TestFileIngestion:
    def test_valid_txt_upload(self, client: TestClient, sample_txt_bytes: bytes) -> None:
        resp = client.post(
            "/api/v1/ingest/file",
            data={"project_id": "proj-file"},
            files={"file": ("notes.txt", sample_txt_bytes, "text/plain")},
        )
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["source_type"] == "txt_file"
        assert data["project_id"] == "proj-file"
        assert data["metadata"]["filename"] == "notes.txt"
        assert data["metadata"]["file_extension"] == ".txt"
        assert data["metadata"]["char_count"] > 0
        assert data["storage_path"] is not None

    def test_valid_pdf_upload(self, client: TestClient, sample_pdf_bytes: bytes) -> None:
        resp = client.post(
            "/api/v1/ingest/file",
            data={"project_id": "proj-pdf"},
            files={"file": ("report.pdf", sample_pdf_bytes, "application/pdf")},
        )
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["source_type"] == "pdf_file"
        assert data["metadata"]["file_extension"] == ".pdf"
        assert data["metadata"]["page_count"] >= 1
        assert data["metadata"]["char_count"] > 0
        assert "pages" in data["metadata"]
        assert data["storage_path"] is not None

    def test_pdf_page_metadata_structure(self, client: TestClient, sample_pdf_bytes: bytes) -> None:
        resp = client.post(
            "/api/v1/ingest/file",
            data={"project_id": "proj-pdf"},
            files={"file": ("report.pdf", sample_pdf_bytes, "application/pdf")},
        )
        assert resp.status_code == 201
        pages = resp.json()["data"]["metadata"]["pages"]
        assert isinstance(pages, list)
        assert len(pages) >= 1
        first_page = pages[0]
        assert "page_number" in first_page
        assert "char_count" in first_page
        assert "text_preview" in first_page

    def test_unsupported_extension_rejected(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/ingest/file",
            data={"project_id": "proj-001"},
            files={"file": ("doc.docx", b"some bytes", "application/octet-stream")},
        )
        assert resp.status_code == 400
        assert "not supported" in resp.json()["detail"].lower()

    def test_empty_file_rejected(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/ingest/file",
            data={"project_id": "proj-001"},
            files={"file": ("empty.txt", b"", "text/plain")},
        )
        assert resp.status_code == 400

    def test_malformed_pdf_rejected(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/ingest/file",
            data={"project_id": "proj-001"},
            files={"file": ("bad.pdf", b"not a real pdf content", "application/pdf")},
        )
        assert resp.status_code == 400

    def test_missing_project_id_rejected(self, client: TestClient, sample_txt_bytes: bytes) -> None:
        resp = client.post(
            "/api/v1/ingest/file",
            files={"file": ("notes.txt", sample_txt_bytes, "text/plain")},
        )
        assert resp.status_code == 422

    def test_invalid_project_id_rejected(self, client: TestClient, sample_txt_bytes: bytes) -> None:
        resp = client.post(
            "/api/v1/ingest/file",
            data={"project_id": "invalid project id!"},
            files={"file": ("notes.txt", sample_txt_bytes, "text/plain")},
        )
        assert resp.status_code == 400

    def test_raw_file_is_persisted(
        self, client: TestClient, sample_txt_bytes: bytes, tmp_storage: dict
    ) -> None:
        resp = client.post(
            "/api/v1/ingest/file",
            data={"project_id": "proj-persist"},
            files={"file": ("persist_test.txt", sample_txt_bytes, "text/plain")},
        )
        assert resp.status_code == 201
        raw_files = list(tmp_storage["raw"].iterdir())
        assert len(raw_files) == 1

    def test_processed_json_is_persisted(
        self, client: TestClient, sample_txt_bytes: bytes, tmp_storage: dict
    ) -> None:
        resp = client.post(
            "/api/v1/ingest/file",
            data={"project_id": "proj-persist"},
            files={"file": ("persist_test.txt", sample_txt_bytes, "text/plain")},
        )
        assert resp.status_code == 201
        comm_id = resp.json()["data"]["communication_id"]
        processed_file = tmp_storage["processed"] / f"{comm_id}.json"
        assert processed_file.exists()

    def test_path_traversal_filename_is_sanitized(
        self, client: TestClient, sample_txt_bytes: bytes, tmp_storage: dict
    ) -> None:
        resp = client.post(
            "/api/v1/ingest/file",
            data={"project_id": "proj-001"},
            files={"file": ("../../etc/passwd.txt", sample_txt_bytes, "text/plain")},
        )
        assert resp.status_code == 201
        # No file should be written outside tmp_storage/raw
        raw_files = list(tmp_storage["raw"].iterdir())
        assert all(f.parent == tmp_storage["raw"] for f in raw_files)


# ---------------------------------------------------------------------------
# GET /api/v1/ingest/{communication_id} — Retrieval
# ---------------------------------------------------------------------------


class TestRetrieval:
    def test_retrieve_by_communication_id(self, client: TestClient) -> None:
        post_resp = client.post(
            "/api/v1/ingest/text",
            json={"project_id": "proj-ret", "content": "Retrieve me", "source_type": "text"},
        )
        assert post_resp.status_code == 201
        comm_id = post_resp.json()["data"]["communication_id"]

        get_resp = client.get(f"/api/v1/ingest/{comm_id}")
        assert get_resp.status_code == 200
        data = get_resp.json()["data"]
        assert data["communication_id"] == comm_id
        assert data["raw_content"] == "Retrieve me"

    def test_unknown_communication_id_returns_404(self, client: TestClient) -> None:
        resp = client.get("/api/v1/ingest/00000000-0000-0000-0000-000000000000")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# GET /api/v1/ingest/project/{project_id} — Project listing
# ---------------------------------------------------------------------------


class TestProjectListing:
    def test_list_communications_by_project(self, client: TestClient) -> None:
        for i in range(3):
            client.post(
                "/api/v1/ingest/text",
                json={
                    "project_id": "proj-list",
                    "content": f"Communication {i}",
                    "source_type": "text",
                },
            )

        resp = client.get("/api/v1/ingest/project/proj-list")
        assert resp.status_code == 200
        body = resp.json()
        assert body["project_id"] == "proj-list"
        assert body["count"] == 3
        assert len(body["data"]) == 3

    def test_only_own_project_communications_returned(self, client: TestClient) -> None:
        client.post(
            "/api/v1/ingest/text",
            json={"project_id": "proj-A", "content": "Project A comm", "source_type": "text"},
        )
        client.post(
            "/api/v1/ingest/text",
            json={"project_id": "proj-B", "content": "Project B comm", "source_type": "text"},
        )

        resp = client.get("/api/v1/ingest/project/proj-A")
        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] == 1
        assert body["data"][0]["project_id"] == "proj-A"

    def test_empty_project_returns_zero_records(self, client: TestClient) -> None:
        resp = client.get("/api/v1/ingest/project/proj-nonexistent")
        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] == 0
        assert body["data"] == []

    def test_listing_is_newest_first(self, client: TestClient) -> None:
        import time

        for i in range(3):
            client.post(
                "/api/v1/ingest/text",
                json={
                    "project_id": "proj-order",
                    "content": f"Message {i}",
                    "source_type": "text",
                },
            )
            time.sleep(0.01)  # small delay to ensure distinct timestamps

        resp = client.get("/api/v1/ingest/project/proj-order")
        assert resp.status_code == 200
        timestamps = [r["timestamp"] for r in resp.json()["data"]]
        assert timestamps == sorted(timestamps, reverse=True)

    def test_invalid_project_id_returns_400(self, client: TestClient) -> None:
        resp = client.get("/api/v1/ingest/project/invalid id!")
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


def test_health_endpoint(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
