"""
ArchScale — Module 1: Communication Ingestion Layer
Utility: PDF text extraction via pypdf.
"""

from __future__ import annotations

import io
from dataclasses import dataclass

try:
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError
except ImportError as exc:  # pragma: no cover
    raise ImportError("pypdf is required. Install it with: pip install pypdf") from exc


@dataclass
class PDFExtractionResult:
    """Result of extracting text from a PDF."""

    text: str
    page_count: int
    char_count: int
    pages: list[dict[str, object]]  # [{page_number, char_count, text_preview}]


class PDFExtractionError(Exception):
    """Raised when PDF text extraction fails."""


def extract_text_from_pdf(pdf_bytes: bytes) -> PDFExtractionResult:
    """
    Extract plain text from a PDF supplied as raw bytes.

    Preserves per-page information in the result.

    Args:
        pdf_bytes: Raw bytes of the PDF file.

    Returns:
        PDFExtractionResult with full text and per-page metadata.

    Raises:
        PDFExtractionError: If the PDF cannot be parsed or yields no text.
    """
    if not pdf_bytes:
        raise PDFExtractionError("PDF content is empty.")

    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
    except PdfReadError as exc:
        raise PDFExtractionError(f"Malformed PDF: {exc}") from exc
    except Exception as exc:
        raise PDFExtractionError(f"Failed to read PDF: {exc}") from exc

    page_count = len(reader.pages)
    if page_count == 0:
        raise PDFExtractionError("PDF contains no pages.")

    pages: list[dict[str, object]] = []
    text_parts: list[str] = []

    for i, page in enumerate(reader.pages, start=1):
        try:
            page_text = page.extract_text() or ""
        except Exception:
            page_text = ""

        pages.append(
            {
                "page_number": i,
                "char_count": len(page_text),
                "text_preview": page_text[:120].replace("\n", " "),
            }
        )

        if page_text.strip():
            text_parts.append(f"--- Page {i} ---\n{page_text.strip()}")

    full_text = "\n\n".join(text_parts)

    if not full_text.strip():
        raise PDFExtractionError(
            "PDF contains no extractable text. "
            "Scanned/image-only PDFs are not supported (OCR not enabled)."
        )

    return PDFExtractionResult(
        text=full_text,
        page_count=page_count,
        char_count=len(full_text),
        pages=pages,
    )
