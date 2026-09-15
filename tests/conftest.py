"""
ArchScale — Module 1 Test Configuration
Shared fixtures for the test suite.
"""

from __future__ import annotations

import io
import struct
import zlib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.ingestion import get_service
from app.main import create_app
from app.services.ingestion_service import IngestionService


# ---------------------------------------------------------------------------
# Isolated storage fixture
# ---------------------------------------------------------------------------


@pytest.fixture()
def tmp_storage(tmp_path: Path) -> dict[str, Path]:
    """
    Provide isolated temporary storage directories for each test.
    Returns a dict with 'raw' and 'processed' paths.
    """
    raw = tmp_path / "raw"
    processed = tmp_path / "processed"
    raw.mkdir()
    processed.mkdir()
    return {"raw": raw, "processed": processed}


# ---------------------------------------------------------------------------
# Service fixture
# ---------------------------------------------------------------------------


@pytest.fixture()
def service(tmp_storage: dict[str, Path]) -> IngestionService:
    """Return an IngestionService wired to temporary storage."""
    return IngestionService(
        raw_path=tmp_storage["raw"],
        processed_path=tmp_storage["processed"],
    )


# ---------------------------------------------------------------------------
# FastAPI test client fixture
# ---------------------------------------------------------------------------


@pytest.fixture()
def client(tmp_storage: dict[str, Path]) -> TestClient:
    """
    Return a FastAPI TestClient backed by isolated temporary storage.
    Overrides the shared service instance so tests don't touch real storage.
    """
    isolated_service = IngestionService(
        raw_path=tmp_storage["raw"],
        processed_path=tmp_storage["processed"],
    )

    app = create_app()
    app.dependency_overrides[get_service] = lambda: isolated_service

    # Patch the module-level service in the ingestion router
    import app.api.ingestion as ingestion_module

    original_service = ingestion_module._service
    ingestion_module._service = isolated_service

    with TestClient(app) as c:
        yield c

    ingestion_module._service = original_service


# ---------------------------------------------------------------------------
# Sample file helpers
# ---------------------------------------------------------------------------


@pytest.fixture()
def sample_txt_bytes() -> bytes:
    return b"This is a sample project communication.\nSecond line of text."


@pytest.fixture()
def sample_pdf_bytes() -> bytes:
    """Return a minimal, valid single-page PDF with extractable text."""
    return _make_minimal_pdf("Hello from ArchScale PDF test.")


def _make_minimal_pdf(text: str) -> bytes:
    """
    Build a minimal valid PDF containing the given text using only stdlib.
    This avoids requiring reportlab or fpdf in the test dependencies.
    """
    # PDF structure: header, objects, xref, trailer
    objects: list[bytes] = []
    offsets: list[int] = []

    def add_obj(content: bytes) -> int:
        obj_num = len(objects) + 1
        objects.append(content)
        return obj_num

    # Object 1: Catalog
    catalog_content = b"<< /Type /Catalog /Pages 2 0 R >>"

    # Object 2: Pages
    pages_content = b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>"

    # Object 3: Page
    page_content = b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>"

    # Object 4: Content stream
    stream_text = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode("latin-1")
    stream_obj = (
        b"<< /Length " + str(len(stream_text)).encode() + b" >>\nstream\n"
        + stream_text
        + b"\nendstream"
    )

    # Object 5: Font
    font_content = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"

    raw_objects = [
        catalog_content,
        pages_content,
        page_content,
        stream_obj,
        font_content,
    ]

    # Build PDF body
    body = b"%PDF-1.4\n"
    xref_offsets: list[int] = []

    for i, obj_body in enumerate(raw_objects, start=1):
        xref_offsets.append(len(body))
        body += f"{i} 0 obj\n".encode()
        body += obj_body
        body += b"\nendobj\n"

    # Cross-reference table
    xref_offset = len(body)
    xref = f"xref\n0 {len(raw_objects) + 1}\n"
    xref += "0000000000 65535 f \n"
    for off in xref_offsets:
        xref += f"{off:010d} 00000 n \n"
    body += xref.encode()

    # Trailer
    trailer = (
        f"trailer\n<< /Size {len(raw_objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF\n"
    )
    body += trailer.encode()

    return body
