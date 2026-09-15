"""
ArchScale — Module 1 Tests
Tests for input validation utilities.
"""

from __future__ import annotations

import pytest

from app.utils.validators import (
    sanitize_filename,
    validate_file_extension,
    validate_project_id,
    validate_text_content,
)


# ---------------------------------------------------------------------------
# validate_project_id
# ---------------------------------------------------------------------------


class TestValidateProjectId:
    def test_valid_alphanumeric(self) -> None:
        ok, err = validate_project_id("proj123")
        assert ok is True
        assert err is None

    def test_valid_with_hyphens(self) -> None:
        ok, err = validate_project_id("proj-001-alpha")
        assert ok is True

    def test_valid_with_underscores(self) -> None:
        ok, err = validate_project_id("proj_alpha_v2")
        assert ok is True

    def test_none_rejected(self) -> None:
        ok, err = validate_project_id(None)
        assert ok is False
        assert err is not None

    def test_empty_string_rejected(self) -> None:
        ok, err = validate_project_id("")
        assert ok is False
        assert "empty" in err.lower() or "required" in err.lower()

    def test_whitespace_only_rejected(self) -> None:
        ok, err = validate_project_id("   ")
        assert ok is False
        assert err is not None

    def test_spaces_rejected(self) -> None:
        ok, err = validate_project_id("invalid id")
        assert ok is False

    def test_special_chars_rejected(self) -> None:
        ok, err = validate_project_id("proj!@#$")
        assert ok is False

    def test_too_long_rejected(self) -> None:
        ok, err = validate_project_id("a" * 129)
        assert ok is False

    def test_max_length_accepted(self) -> None:
        ok, err = validate_project_id("a" * 128)
        assert ok is True


# ---------------------------------------------------------------------------
# validate_text_content
# ---------------------------------------------------------------------------


class TestValidateTextContent:
    def test_valid_content(self) -> None:
        ok, err = validate_text_content("Meeting notes from today.")
        assert ok is True
        assert err is None

    def test_none_rejected(self) -> None:
        ok, err = validate_text_content(None)
        assert ok is False

    def test_empty_string_rejected(self) -> None:
        ok, err = validate_text_content("")
        assert ok is False
        assert "empty" in err.lower()

    def test_whitespace_only_rejected(self) -> None:
        ok, err = validate_text_content("   \n\t  ")
        assert ok is False

    def test_single_char_accepted(self) -> None:
        ok, err = validate_text_content("x")
        assert ok is True

    def test_multiline_content_accepted(self) -> None:
        ok, err = validate_text_content("Line 1\nLine 2\nLine 3")
        assert ok is True


# ---------------------------------------------------------------------------
# sanitize_filename
# ---------------------------------------------------------------------------


class TestSanitizeFilename:
    def test_normal_filename(self) -> None:
        assert sanitize_filename("report.pdf") == "report.pdf"

    def test_strips_directory_components(self) -> None:
        result = sanitize_filename("../../etc/passwd.txt")
        assert "/" not in result
        assert "\\" not in result
        assert "passwd.txt" in result

    def test_windows_path_stripped(self) -> None:
        result = sanitize_filename("C:\\Users\\secret\\file.txt")
        assert "C:" not in result
        assert result.endswith(".txt")

    def test_special_chars_replaced(self) -> None:
        result = sanitize_filename("my file (1).txt")
        assert " " not in result
        assert result.endswith(".txt")

    def test_max_length_enforced(self) -> None:
        long_name = "a" * 300 + ".txt"
        result = sanitize_filename(long_name)
        assert len(result) <= 200

    def test_null_bytes_removed(self) -> None:
        result = sanitize_filename("file\x00name.txt")
        assert "\x00" not in result


# ---------------------------------------------------------------------------
# validate_file_extension
# ---------------------------------------------------------------------------


class TestValidateFileExtension:
    ALLOWED = {".txt", ".pdf"}

    def test_txt_allowed(self) -> None:
        ok, result = validate_file_extension("notes.txt", self.ALLOWED)
        assert ok is True
        assert result == ".txt"

    def test_pdf_allowed(self) -> None:
        ok, result = validate_file_extension("report.pdf", self.ALLOWED)
        assert ok is True
        assert result == ".pdf"

    def test_case_insensitive(self) -> None:
        ok, result = validate_file_extension("report.PDF", self.ALLOWED)
        assert ok is True
        assert result == ".pdf"

    def test_docx_rejected(self) -> None:
        ok, msg = validate_file_extension("doc.docx", self.ALLOWED)
        assert ok is False
        assert "not supported" in msg.lower()

    def test_no_extension_rejected(self) -> None:
        ok, msg = validate_file_extension("noextension", self.ALLOWED)
        assert ok is False

    def test_dot_only_rejected(self) -> None:
        # "file." has an empty extension part — treated as no valid extension
        ok, msg = validate_file_extension("file.", self.ALLOWED)
        assert ok is False
