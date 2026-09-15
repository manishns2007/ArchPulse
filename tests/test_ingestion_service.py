"""
ArchScale — Module 1 Tests
Tests for the IngestionService business logic layer.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.models.communication import IngestionStatus, SourceType
from app.services.ingestion_service import IngestionError, IngestionService


# ---------------------------------------------------------------------------
# Text ingestion
# ---------------------------------------------------------------------------


class TestServiceTextIngestion:
    def test_valid_text_returns_record(self, service: IngestionService) -> None:
        record = service.ingest_text(
            project_id="proj-svc",
            content="The foundation work begins on Monday.",
            source_type=SourceType.text,
        )
        assert record.project_id == "proj-svc"
        assert record.source_type == SourceType.text
        assert record.status == IngestionStatus.ingested
        assert record.raw_content == "The foundation work begins on Monday."
        assert record.storage_path is None
        assert record.metadata["char_count"] > 0

    def test_transcript_ingestion(self, service: IngestionService) -> None:
        record = service.ingest_text(
            project_id="proj-trans",
            content="PM: Go-live is June 10th. Dev: Understood.",
            source_type=SourceType.transcript,
        )
        assert record.source_type == SourceType.transcript

    def test_empty_content_raises(self, service: IngestionService) -> None:
        with pytest.raises(IngestionError, match="empty"):
            service.ingest_text(project_id="proj-svc", content="", source_type=SourceType.text)

    def test_whitespace_content_raises(self, service: IngestionService) -> None:
        with pytest.raises(IngestionError):
            service.ingest_text(
                project_id="proj-svc", content="   \n\t  ", source_type=SourceType.text
            )

    def test_invalid_project_id_raises(self, service: IngestionService) -> None:
        with pytest.raises(IngestionError, match="project_id"):
            service.ingest_text(
                project_id="invalid id!", content="valid content", source_type=SourceType.text
            )

    def test_blank_project_id_raises(self, service: IngestionService) -> None:
        with pytest.raises(IngestionError, match="project_id"):
            service.ingest_text(
                project_id="   ", content="valid content", source_type=SourceType.text
            )

    def test_invalid_source_type_raises(self, service: IngestionService) -> None:
        with pytest.raises(IngestionError, match="source_type"):
            service.ingest_text(
                project_id="proj-svc",
                content="valid content",
                source_type=SourceType.pdf_file,  # not allowed for text
            )

    def test_content_is_trimmed(self, service: IngestionService) -> None:
        record = service.ingest_text(
            project_id="proj-svc",
            content="  hello world  \n",
            source_type=SourceType.text,
        )
        assert record.raw_content == "hello world"

    def test_communication_id_is_unique(self, service: IngestionService) -> None:
        ids = {
            service.ingest_text(
                project_id="proj-svc", content=f"message {i}", source_type=SourceType.text
            ).communication_id
            for i in range(5)
        }
        assert len(ids) == 5

    def test_processed_json_written(
        self, service: IngestionService, tmp_storage: dict[str, Path]
    ) -> None:
        record = service.ingest_text(
            project_id="proj-svc", content="Persist me", source_type=SourceType.text
        )
        processed_file = tmp_storage["processed"] / f"{record.communication_id}.json"
        assert processed_file.exists()
        content = processed_file.read_text(encoding="utf-8")
        assert record.communication_id in content


# ---------------------------------------------------------------------------
# TXT file ingestion
# ---------------------------------------------------------------------------


class TestServiceTxtIngestion:
    def test_valid_txt_ingestion(
        self, service: IngestionService, sample_txt_bytes: bytes
    ) -> None:
        record = service.ingest_file(
            project_id="proj-txt",
            filename="notes.txt",
            file_bytes=sample_txt_bytes,
        )
        assert record.source_type == SourceType.txt_file
        assert record.metadata["file_extension"] == ".txt"
        assert record.metadata["filename"] == "notes.txt"
        assert record.storage_path is not None

    def test_raw_file_written(
        self,
        service: IngestionService,
        sample_txt_bytes: bytes,
        tmp_storage: dict[str, Path],
    ) -> None:
        record = service.ingest_file(
            project_id="proj-txt",
            filename="notes.txt",
            file_bytes=sample_txt_bytes,
        )
        raw_files = list(tmp_storage["raw"].iterdir())
        assert len(raw_files) == 1
        assert raw_files[0].read_bytes() == sample_txt_bytes

    def test_empty_txt_raises(self, service: IngestionService) -> None:
        with pytest.raises(IngestionError, match="empty"):
            service.ingest_file(project_id="proj-txt", filename="empty.txt", file_bytes=b"")

    def test_whitespace_txt_raises(self, service: IngestionService) -> None:
        with pytest.raises(IngestionError):
            service.ingest_file(
                project_id="proj-txt", filename="ws.txt", file_bytes=b"   \n\t  "
            )

    def test_txt_char_count_in_metadata(
        self, service: IngestionService, sample_txt_bytes: bytes
    ) -> None:
        record = service.ingest_file(
            project_id="proj-txt", filename="notes.txt", file_bytes=sample_txt_bytes
        )
        assert record.metadata["char_count"] == len(record.raw_content)


# ---------------------------------------------------------------------------
# PDF file ingestion
# ---------------------------------------------------------------------------


class TestServicePdfIngestion:
    def test_valid_pdf_ingestion(
        self, service: IngestionService, sample_pdf_bytes: bytes
    ) -> None:
        record = service.ingest_file(
            project_id="proj-pdf",
            filename="report.pdf",
            file_bytes=sample_pdf_bytes,
        )
        assert record.source_type == SourceType.pdf_file
        assert record.metadata["file_extension"] == ".pdf"
        assert record.metadata["page_count"] >= 1
        assert "pages" in record.metadata
        assert record.storage_path is not None

    def test_pdf_page_metadata(
        self, service: IngestionService, sample_pdf_bytes: bytes
    ) -> None:
        record = service.ingest_file(
            project_id="proj-pdf",
            filename="report.pdf",
            file_bytes=sample_pdf_bytes,
        )
        pages = record.metadata["pages"]
        assert isinstance(pages, list)
        assert all("page_number" in p for p in pages)
        assert all("char_count" in p for p in pages)

    def test_malformed_pdf_raises(self, service: IngestionService) -> None:
        with pytest.raises(IngestionError):
            service.ingest_file(
                project_id="proj-pdf",
                filename="bad.pdf",
                file_bytes=b"not a real pdf",
            )

    def test_raw_pdf_persisted(
        self,
        service: IngestionService,
        sample_pdf_bytes: bytes,
        tmp_storage: dict[str, Path],
    ) -> None:
        service.ingest_file(
            project_id="proj-pdf",
            filename="report.pdf",
            file_bytes=sample_pdf_bytes,
        )
        raw_files = list(tmp_storage["raw"].iterdir())
        assert len(raw_files) == 1
        assert raw_files[0].suffix == ".pdf"


# ---------------------------------------------------------------------------
# Unsupported extensions
# ---------------------------------------------------------------------------


class TestServiceUnsupportedExtensions:
    def test_docx_rejected(self, service: IngestionService) -> None:
        with pytest.raises(IngestionError, match="not supported"):
            service.ingest_file(
                project_id="proj-001",
                filename="document.docx",
                file_bytes=b"some content",
            )

    def test_no_extension_rejected(self, service: IngestionService) -> None:
        with pytest.raises(IngestionError):
            service.ingest_file(
                project_id="proj-001",
                filename="noextension",
                file_bytes=b"some content",
            )


# ---------------------------------------------------------------------------
# Retrieval and listing
# ---------------------------------------------------------------------------


class TestServiceRetrieval:
    def test_get_existing_record(self, service: IngestionService) -> None:
        record = service.ingest_text(
            project_id="proj-ret", content="Hello retrieval", source_type=SourceType.text
        )
        retrieved = service.get_communication(record.communication_id)
        assert retrieved is not None
        assert retrieved.communication_id == record.communication_id
        assert retrieved.raw_content == "Hello retrieval"

    def test_get_nonexistent_record_returns_none(self, service: IngestionService) -> None:
        result = service.get_communication("00000000-0000-0000-0000-000000000000")
        assert result is None

    def test_list_project_communications(self, service: IngestionService) -> None:
        for i in range(4):
            service.ingest_text(
                project_id="proj-list",
                content=f"Message {i}",
                source_type=SourceType.text,
            )
        records = service.list_project_communications("proj-list")
        assert len(records) == 4
        assert all(r.project_id == "proj-list" for r in records)

    def test_list_excludes_other_projects(self, service: IngestionService) -> None:
        service.ingest_text(project_id="proj-A", content="A message", source_type=SourceType.text)
        service.ingest_text(project_id="proj-B", content="B message", source_type=SourceType.text)
        records = service.list_project_communications("proj-A")
        assert len(records) == 1
        assert records[0].project_id == "proj-A"

    def test_list_returns_newest_first(self, service: IngestionService) -> None:
        import time

        for i in range(3):
            service.ingest_text(
                project_id="proj-order",
                content=f"Order {i}",
                source_type=SourceType.text,
            )
            time.sleep(0.01)

        records = service.list_project_communications("proj-order")
        timestamps = [r.timestamp for r in records]
        assert timestamps == sorted(timestamps, reverse=True)

    def test_list_empty_project(self, service: IngestionService) -> None:
        records = service.list_project_communications("proj-empty")
        assert records == []
