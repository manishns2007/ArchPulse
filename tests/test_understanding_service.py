"""
ArchScale — Module 2 Tests
Tests for the CommunicationUnderstandingService (business logic layer).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from app.llm.provider import FakeLLMProvider, _default_fake_response
from app.models.communication import CommunicationRecord, IngestionStatus, SourceType
from app.models.understanding import VALID_COMMUNICATION_TYPES, UnderstandingResult
from app.services.understanding_service import (
    CommunicationUnderstandingService,
    UnderstandingError,
    UnderstandingProviderError,
    UnderstandingValidationError,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_record(
    raw_content: str = "Client approved the revised kitchen layout.",
    project_id: str = "proj-villa",
    source_type: SourceType = SourceType.text,
) -> CommunicationRecord:
    return CommunicationRecord(
        project_id=project_id,
        communication_id="test-comm-001",
        source_type=source_type,
        timestamp=datetime.now(timezone.utc),
        raw_content=raw_content,
        metadata={"char_count": len(raw_content)},
        storage_path=None,
        status=IngestionStatus.ingested,
    )


def _make_service(
    fixed_response: dict | None = None,
    should_fail: bool = False,
    bad_json: bool = False,
) -> CommunicationUnderstandingService:
    provider = FakeLLMProvider(
        fixed_response=fixed_response,
        should_fail=should_fail,
        bad_json=bad_json,
    )
    return CommunicationUnderstandingService(llm_provider=provider)


# ---------------------------------------------------------------------------
# Successful understanding
# ---------------------------------------------------------------------------


class TestUnderstandingServiceSuccess:
    def test_valid_record_returns_result(self) -> None:
        svc = _make_service()
        record = _make_record()
        result = svc.analyze(record)

        assert isinstance(result, UnderstandingResult)
        assert result.project_id == record.project_id
        assert result.communication_id == record.communication_id

    def test_result_has_all_required_fields(self) -> None:
        svc = _make_service()
        result = svc.analyze(_make_record())

        assert result.concise_summary
        assert result.detailed_summary
        assert isinstance(result.topics, list)
        assert isinstance(result.stakeholders, list)
        assert result.communication_type in VALID_COMMUNICATION_TYPES
        assert isinstance(result.important_context, list)

    def test_traceability_fields_preserved(self) -> None:
        record = _make_record(project_id="proj-bridge", raw_content="Something happened.")
        record = CommunicationRecord(
            project_id="proj-bridge",
            communication_id="specific-uuid-001",
            source_type=SourceType.text,
            timestamp=datetime.now(timezone.utc),
            raw_content="Something happened.",
            metadata={},
            status=IngestionStatus.ingested,
        )
        svc = _make_service()
        result = svc.analyze(record)

        assert result.project_id == "proj-bridge"
        assert result.communication_id == "specific-uuid-001"

    def test_analyzed_at_is_set(self) -> None:
        svc = _make_service()
        result = svc.analyze(_make_record())
        assert result.analyzed_at is not None

    def test_llm_model_is_set(self) -> None:
        svc = _make_service()
        result = svc.analyze(_make_record())
        assert result.llm_model  # non-empty string

    def test_transcript_source_type(self) -> None:
        svc = _make_service()
        record = _make_record(
            raw_content="PM: Go-live is June 10th.\nDev: Confirmed.",
            source_type=SourceType.transcript,
        )
        result = svc.analyze(record)
        assert result.project_id == record.project_id

    def test_topics_are_non_empty_strings(self) -> None:
        svc = _make_service()
        result = svc.analyze(_make_record())
        for topic in result.topics:
            assert topic.strip()

    def test_stakeholders_are_non_empty_strings(self) -> None:
        svc = _make_service()
        result = svc.analyze(_make_record())
        for stakeholder in result.stakeholders:
            assert stakeholder.strip()

    def test_markdown_fence_stripped_from_response(self) -> None:
        """Service must correctly handle LLM wrapping JSON in ``` fences."""
        fake_data = _default_fake_response()
        fenced_text = f"```json\n{json.dumps(fake_data)}\n```"

        from app.llm.base import LLMRequest, LLMResponse
        from app.llm.base import LLMProvider

        class FencedProvider(LLMProvider):
            @property
            def provider_name(self) -> str:
                return "fenced-fake"

            def generate(self, request: LLMRequest) -> LLMResponse:
                return LLMResponse(text=fenced_text, model="fenced")

        svc = CommunicationUnderstandingService(llm_provider=FencedProvider())
        result = svc.analyze(_make_record())
        assert isinstance(result, UnderstandingResult)

    def test_communication_type_unknown_fallback(self) -> None:
        """If LLM returns an invalid type, it should fall back to 'unknown'."""
        response_data = _default_fake_response()
        response_data["communication_type"] = "totally_invalid_type"
        svc = _make_service(fixed_response=response_data)
        result = svc.analyze(_make_record())
        assert result.communication_type == "unknown"


# ---------------------------------------------------------------------------
# Input validation failures
# ---------------------------------------------------------------------------


class TestUnderstandingServiceInputValidation:
    def test_empty_raw_content_raises(self) -> None:
        svc = _make_service()
        # Force a record with empty content (bypass Pydantic min_length by post-setting)
        record = _make_record("valid content")
        object.__setattr__(record, "raw_content", "")
        with pytest.raises(UnderstandingError, match="empty"):
            svc.analyze(record)

    def test_whitespace_only_content_raises(self) -> None:
        svc = _make_service()
        record = _make_record("valid content")
        object.__setattr__(record, "raw_content", "   \n\t  ")
        with pytest.raises(UnderstandingError):
            svc.analyze(record)


# ---------------------------------------------------------------------------
# LLM failure modes
# ---------------------------------------------------------------------------


class TestUnderstandingServiceFailureModes:
    def test_provider_failure_raises_provider_error(self) -> None:
        svc = _make_service(should_fail=True)
        with pytest.raises(UnderstandingProviderError, match="provider"):
            svc.analyze(_make_record())

    def test_bad_json_raises_validation_error(self) -> None:
        svc = _make_service(bad_json=True)
        with pytest.raises(UnderstandingValidationError, match="JSON"):
            svc.analyze(_make_record())

    def test_missing_required_field_raises_validation_error(self) -> None:
        """Drop a required field from the fake response to simulate partial LLM output."""
        incomplete = _default_fake_response()
        del incomplete["concise_summary"]
        svc = _make_service(fixed_response=incomplete)
        with pytest.raises(UnderstandingValidationError):
            svc.analyze(_make_record())

    def test_wrong_type_for_topics_raises_validation_error(self) -> None:
        """topics must be a list, not a string."""
        bad_data = _default_fake_response()
        bad_data["topics"] = "not a list"
        svc = _make_service(fixed_response=bad_data)
        with pytest.raises(UnderstandingValidationError):
            svc.analyze(_make_record())

    def test_empty_response_text_raises_provider_error(self) -> None:
        from app.llm.base import LLMProvider, LLMRequest, LLMResponse

        class EmptyProvider(LLMProvider):
            @property
            def provider_name(self) -> str:
                return "empty"

            def generate(self, request: LLMRequest) -> LLMResponse:
                return LLMResponse(text="", model="empty")

        svc = CommunicationUnderstandingService(llm_provider=EmptyProvider())
        with pytest.raises(UnderstandingProviderError):
            svc.analyze(_make_record())


# ---------------------------------------------------------------------------
# UnderstandingResult schema
# ---------------------------------------------------------------------------


class TestUnderstandingResultSchema:
    def test_valid_result_construction(self) -> None:
        result = UnderstandingResult(
            project_id="proj-001",
            communication_id="comm-001",
            concise_summary="A short summary.",
            detailed_summary="A longer summary with details.",
            topics=["topic1", "topic2"],
            stakeholders=["Alice", "Bob"],
            communication_type="discussion",
            important_context=["Context A."],
        )
        assert result.project_id == "proj-001"
        assert result.communication_type == "discussion"

    def test_all_valid_communication_types(self) -> None:
        for ct in VALID_COMMUNICATION_TYPES:
            result = UnderstandingResult(
                project_id="p",
                communication_id="c",
                concise_summary="s",
                detailed_summary="d",
                topics=[],
                stakeholders=[],
                communication_type=ct,
                important_context=[],
            )
            assert result.communication_type == ct

    def test_invalid_communication_type_becomes_unknown(self) -> None:
        result = UnderstandingResult(
            project_id="p",
            communication_id="c",
            concise_summary="s",
            detailed_summary="d",
            topics=[],
            stakeholders=[],
            communication_type="garbage_type",
            important_context=[],
        )
        assert result.communication_type == "unknown"

    def test_blank_items_stripped_from_lists(self) -> None:
        result = UnderstandingResult(
            project_id="p",
            communication_id="c",
            concise_summary="s",
            detailed_summary="d",
            topics=["  ", "real topic", ""],
            stakeholders=["  ", "Bob"],
            communication_type="unknown",
            important_context=["  ", "relevant"],
        )
        assert result.topics == ["real topic"]
        assert result.stakeholders == ["Bob"]
        assert result.important_context == ["relevant"]
