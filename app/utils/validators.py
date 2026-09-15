"""
ArchScale — Module 1: Communication Ingestion Layer
Utility: Input validation helpers.
"""

from __future__ import annotations

import re


# Allowed project_id pattern: alphanumeric, hyphens, underscores (1-128 chars)
_PROJECT_ID_RE = re.compile(r"^[a-zA-Z0-9_\-]{1,128}$")


def validate_project_id(project_id: str | None) -> tuple[bool, str | None]:
    """
    Validate a project_id value.

    Returns:
        (True, None) if valid.
        (False, error_message) if invalid.
    """
    if project_id is None or project_id == "":
        return False, "project_id is required and must not be empty."

    stripped = project_id.strip()
    if not stripped:
        return False, "project_id must not be blank."

    if not _PROJECT_ID_RE.match(stripped):
        return (
            False,
            "project_id may only contain letters, digits, hyphens, and underscores "
            "(1–128 characters).",
        )

    return True, None


def validate_text_content(content: str | None) -> tuple[bool, str | None]:
    """
    Validate raw text content for ingestion.

    Returns:
        (True, None) if valid.
        (False, error_message) if invalid.
    """
    if content is None:
        return False, "content is required."
    if not isinstance(content, str):
        return False, "content must be a string."
    if not content.strip():
        return False, "content must not be empty or whitespace-only."
    return True, None


def sanitize_filename(filename: str) -> str:
    """
    Return a filesystem-safe version of the filename.

    - Strips directory components (path traversal protection).
    - Replaces non-alphanumeric chars (except dot, hyphen, underscore) with underscores.
    - Limits to 200 characters.
    """
    # Strip any directory component
    filename = filename.replace("\\", "/").split("/")[-1]
    # Remove null bytes
    filename = filename.replace("\x00", "")
    # Keep only safe characters
    safe = re.sub(r"[^\w.\-]", "_", filename)
    # Collapse repeated underscores
    safe = re.sub(r"_+", "_", safe)
    return safe[:200] or "upload"


def validate_file_extension(filename: str, allowed: set[str]) -> tuple[bool, str | None]:
    """
    Check that the file's extension is in the allowed set.

    Returns:
        (True, None) if allowed.
        (False, error_message) if not.
    """
    parts = filename.rsplit(".", 1)
    if len(parts) < 2:
        return False, f"File has no extension. Allowed: {sorted(allowed)}."

    ext = f".{parts[-1].lower()}"
    if ext not in allowed:
        return False, f"File extension '{ext}' is not supported. Allowed: {sorted(allowed)}."

    return True, ext
