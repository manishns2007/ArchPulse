"""
ArchScale — Module 1: Communication Ingestion Layer
Core ingestion service: orchestrates validation, extraction, and persistence.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from app.config import settings
from app.models.communication import (
    CommunicationRecord,
    IngestionStatus,
    SourceType,
)
from app.utils.pdf_extractor import PDFExtractionError, extract_text_from_pdf
from app.utils.validators import (
    sanitize_filename,
    validate_file_extension,
    validate_project_id,
    validate_text_content,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _ensure_storage_dirs(raw_path: Path, processed_path: Path) -> None:
    """Create storage directories if they do not exist."""
    raw_path.mkdir(parents=True, exist_ok=True)
    processed_path.mkdir(parents=True, exist_ok=True)


def _save_raw_file(data: bytes, filename: str, raw_path: Path) -> str:
    """
    Save raw file bytes to storage/raw/<filename>.
    Returns the relative storage path string.
    """
    dest = raw_path / filename
    dest.write_bytes(data)
    return str(Path(settings.raw_storage_dir) / filename)


def _save_processed(record: CommunicationRecord, processed_path: Path) -> None:
    """Serialize and persist a CommunicationRecord to storage/processed/."""
    dest = processed_path / f"{record.communication_id}.json"
    dest.write_text(
        record.model_dump_json(indent=2),
        encoding="utf-8",
    )


def _load_record(communication_id: str, processed_path: Path) -> CommunicationRecord | None:
    """Load and deserialize a CommunicationRecord from disk. Returns None if not found."""
    dest = processed_path / f"{communication_id}.json"
    if not dest.exists():
        return None
    try:
        return CommunicationRecord.model_validate_json(dest.read_text(encoding="utf-8"))
    except Exception:
        logger.exception("Failed to deserialize record %s", communication_id)
        return None


def _list_records_for_project(
    project_id: str, processed_path: Path
) -> list[CommunicationRecord]:
    """
    Return all CommunicationRecords belonging to project_id,
    sorted newest-first by timestamp.
    """
    records: list[CommunicationRecord] = []
    if not processed_path.exists():
        return records

    for path in processed_path.glob("*.json"):
        record = None
        try:
            record = CommunicationRecord.model_validate_json(
                path.read_text(encoding="utf-8")
            )
        except Exception:
            logger.warning("Skipping unreadable record file: %s", path.name)
            continue

        if record and record.project_id == project_id:
            records.append(record)

    records.sort(
        key=lambda r: r.timestamp if isinstance(r.timestamp, datetime) else datetime.min,
        reverse=True,
    )
    return records


# ---------------------------------------------------------------------------
# Public service functions
# ---------------------------------------------------------------------------


class IngestionError(Exception):
    """Raised when ingestion cannot be completed due to invalid input."""


class IngestionService:
    """
    Stateless service class that encapsulates all ingestion logic.

    Can be instantiated with custom storage paths (useful for testing).
    """

    def __init__(
        self,
        raw_path: Path | None = None,
        processed_path: Path | None = None,
    ) -> None:
        self.raw_path = raw_path or settings.raw_path
        self.processed_path = processed_path or settings.processed_path
        _ensure_storage_dirs(self.raw_path, self.processed_path)

    # ------------------------------------------------------------------
    # Text / Transcript ingestion
    # ------------------------------------------------------------------

    def ingest_text(
        self,
        project_id: str,
        content: str,
        source_type: SourceType = SourceType.text,
    ) -> CommunicationRecord:
        """
        Ingest a pasted text or meeting transcript.

        Args:
            project_id: Owning project identifier.
            content:    Raw text content.
            source_type: Must be SourceType.text or SourceType.transcript.

        Returns:
            Persisted CommunicationRecord.

        Raises:
            IngestionError: On validation failure.
        """
        # Validate project_id
        ok, err = validate_project_id(project_id)
        if not ok:
            raise IngestionError(err)

        # Validate content
        ok, err = validate_text_content(content)
        if not ok:
            raise IngestionError(err)

        # source_type guard
        if source_type not in (SourceType.text, SourceType.transcript):
            raise IngestionError(
                f"source_type '{source_type}' is not valid for text ingestion. "
                "Use 'text' or 'transcript'."
            )

        trimmed = content.strip()

        record = CommunicationRecord(
            project_id=project_id.strip(),
            communication_id=str(uuid4()),
            source_type=source_type,
            timestamp=datetime.now(timezone.utc),
            raw_content=trimmed,
            metadata={
                "source_type": source_type.value
                if isinstance(source_type, SourceType)
                else str(source_type),
                "char_count": len(trimmed),
            },
            storage_path=None,
            status=IngestionStatus.ingested,
        )

        _save_processed(record, self.processed_path)
        logger.info("Ingested text record %s for project %s", record.communication_id, project_id)
        return record

    # ------------------------------------------------------------------
    # File ingestion (TXT + PDF)
    # ------------------------------------------------------------------

    def ingest_file(
        self,
        project_id: str,
        filename: str,
        file_bytes: bytes,
    ) -> CommunicationRecord:
        """
        Ingest an uploaded .txt or .pdf file.

        Args:
            project_id:  Owning project identifier.
            filename:    Original filename from the upload (will be sanitized).
            file_bytes:  Raw bytes of the uploaded file.

        Returns:
            Persisted CommunicationRecord.

        Raises:
            IngestionError: On validation or extraction failure.
        """
        # Validate project_id
        ok, err = validate_project_id(project_id)
        if not ok:
            raise IngestionError(err)

        # Validate file size
        if not file_bytes:
            raise IngestionError("Uploaded file is empty.")
        if len(file_bytes) > settings.max_upload_size_bytes:
            raise IngestionError(
                f"File exceeds the maximum allowed size of "
                f"{settings.max_upload_size_bytes // (1024 * 1024)} MB."
            )

        # Validate extension
        ok, result = validate_file_extension(filename, settings.allowed_extensions_set)
        if not ok:
            raise IngestionError(result)  # result is error message here
        ext: str = result  # type: ignore[assignment]

        safe_name = sanitize_filename(filename)
        communication_id = str(uuid4())

        # Give the raw file a collision-safe name
        raw_filename = f"{communication_id}_{safe_name}"

        if ext == ".txt":
            return self._ingest_txt(
                project_id=project_id,
                communication_id=communication_id,
                file_bytes=file_bytes,
                original_filename=safe_name,
                raw_filename=raw_filename,
            )
        elif ext == ".pdf":
            return self._ingest_pdf(
                project_id=project_id,
                communication_id=communication_id,
                file_bytes=file_bytes,
                original_filename=safe_name,
                raw_filename=raw_filename,
            )
        else:
            # Should never reach here due to extension check above
            raise IngestionError(f"Unsupported file type: {ext}")

    def _ingest_txt(
        self,
        project_id: str,
        communication_id: str,
        file_bytes: bytes,
        original_filename: str,
        raw_filename: str,
    ) -> CommunicationRecord:
        try:
            text = file_bytes.decode("utf-8", errors="replace")
        except Exception as exc:
            raise IngestionError(f"Failed to decode TXT file: {exc}") from exc

        if not text.strip():
            raise IngestionError("Uploaded TXT file contains no readable text content.")

        trimmed = text.strip()
        storage_path = _save_raw_file(file_bytes, raw_filename, self.raw_path)

        record = CommunicationRecord(
            project_id=project_id.strip(),
            communication_id=communication_id,
            source_type=SourceType.txt_file,
            timestamp=datetime.now(timezone.utc),
            raw_content=trimmed,
            metadata={
                "filename": original_filename,
                "file_extension": ".txt",
                "char_count": len(trimmed),
            },
            storage_path=storage_path,
            status=IngestionStatus.ingested,
        )

        _save_processed(record, self.processed_path)
        logger.info("Ingested TXT record %s for project %s", communication_id, project_id)
        return record

    def _ingest_pdf(
        self,
        project_id: str,
        communication_id: str,
        file_bytes: bytes,
        original_filename: str,
        raw_filename: str,
    ) -> CommunicationRecord:
        try:
            result = extract_text_from_pdf(file_bytes)
        except PDFExtractionError as exc:
            raise IngestionError(str(exc)) from exc

        storage_path = _save_raw_file(file_bytes, raw_filename, self.raw_path)

        record = CommunicationRecord(
            project_id=project_id.strip(),
            communication_id=communication_id,
            source_type=SourceType.pdf_file,
            timestamp=datetime.now(timezone.utc),
            raw_content=result.text,
            metadata={
                "filename": original_filename,
                "file_extension": ".pdf",
                "page_count": result.page_count,
                "char_count": result.char_count,
                "pages": result.pages,
            },
            storage_path=storage_path,
            status=IngestionStatus.ingested,
        )

        _save_processed(record, self.processed_path)
        logger.info(
            "Ingested PDF record %s (%d pages) for project %s",
            communication_id,
            result.page_count,
            project_id,
        )
        return record

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    def get_communication(self, communication_id: str) -> CommunicationRecord | None:
        """Retrieve a single CommunicationRecord by ID."""
        return _load_record(communication_id, self.processed_path)

    def list_project_communications(self, project_id: str) -> list[CommunicationRecord]:
        """Return all communications for a project, newest first."""
        return _list_records_for_project(project_id, self.processed_path)
