"""
ArchScale — Module 6 Tests
Unit tests for DecisionService.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.llm.provider import FakeLLMProvider
from app.models.communication import CommunicationRecord, IngestionStatus, SourceType
from app.models.decision import (
    DecisionExtractionResult,
    ExtractedDecision,
    ExtractedDecisionPayload,
    VALID_ITEM_TYPES,
    VALID_STATUSES,
)
from app.models.understanding import UnderstandingResult
from app.services.decision_service import (
    DecisionError,
    DecisionProviderError,
    DecisionService,
    DecisionValidationError,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_record(
    raw_content: str = "Client approved the revised kitchen layout.",
    project_id: str = "proj-villa",
    communication_id: str = "test-comm-001",
    source_type: SourceType = SourceType.text,
) -> CommunicationRecord:
    return CommunicationRecord(
        project_id=project_id,
        communication_id=communication_id,
        source_type=source_type,
        timestamp=datetime(2026, 9, 14, 10, 0, tzinfo=timezone.utc),
        raw_content=raw_content,
        metadata={"char_count": len(raw_content)},
        storage_path=None,
        status=IngestionStatus.ingested,
    )


def _make_understanding(
    project_id: str = "proj-villa",
    communication_id: str = "test-comm-001",
) -> UnderstandingResult:
    return UnderstandingResult(
        project_id=project_id,
        communication_id=communication_id,
        concise_summary="Client approved the kitchen layout.",
        detailed_summary="Client approved the kitchen layout during the site coordination call.",
        topics=["kitchen layout", "approval"],
        stakeholders=["Client", "Architect"],
        communication_type="approval",
        important_context=["Layout is approved for next phase."],
    )


def _make_service(
    fixed_response: dict | None = None,
    should_fail: bool = False,
    bad_json: bool = False,
) -> DecisionService:
    provider = FakeLLMProvider(
        fixed_response=fixed_response,
        should_fail=should_fail,
        bad_json=bad_json,
    )
    return DecisionService(llm_provider=provider)


# ---------------------------------------------------------------------------
# Success Cases: Decisions & Approvals Extraction
# ---------------------------------------------------------------------------


class TestDecisionServiceSuccess:
    def test_explicit_decision_extraction(self) -> None:
        custom_response = {
            "decisions": [
                {
                    "item_type": "decision",
                    "description": "Use granite for the kitchen counter",
                    "subject": "kitchen counter",
                    "status": "decided",
                    "evidence": "We decided to use granite for the kitchen counter.",
                    "confidence": 0.95,
                }
            ]
        }
        svc = _make_service(fixed_response=custom_response)
        record = _make_record(raw_content="We decided to use granite for the kitchen counter.")
        result = svc.extract_decisions(record)

        assert isinstance(result, DecisionExtractionResult)
        assert len(result.decisions) == 1
        item = result.decisions[0]
        assert item.item_type == "decision"
        assert item.description == "Use granite for the kitchen counter"
        assert item.subject == "kitchen counter"
        assert item.status == "decided"
        assert item.evidence == "We decided to use granite for the kitchen counter."
        assert item.confidence == 0.95

        # Validate UUID4
        uuid_obj = UUID(item.decision_id)
        assert uuid_obj.version == 4

    def test_explicit_approval_extraction(self) -> None:
        custom_response = {
            "decisions": [
                {
                    "item_type": "approval",
                    "description": "Revised kitchen layout was approved by the client",
                    "subject": "kitchen layout",
                    "status": "approved",
                    "evidence": "Client approved the revised kitchen layout.",
                    "confidence": 0.98,
                }
            ]
        }
        svc = _make_service(fixed_response=custom_response)
        record = _make_record(raw_content="Client approved the revised kitchen layout.")
        result = svc.extract_decisions(record)

        assert len(result.decisions) == 1
        item = result.decisions[0]
        assert item.item_type == "approval"
        assert item.status == "approved"
        assert item.evidence == "Client approved the revised kitchen layout."

    def test_explicit_rejection_extraction(self) -> None:
        custom_response = {
            "decisions": [
                {
                    "item_type": "decision",
                    "description": "Reject the dark wood finish",
                    "subject": "wood finish",
                    "status": "rejected",
                    "evidence": "Client formally rejected the dark wood finish.",
                    "confidence": 0.96,
                }
            ]
        }
        svc = _make_service(fixed_response=custom_response)
        record = _make_record(raw_content="Client formally rejected the dark wood finish.")
        result = svc.extract_decisions(record)

        assert len(result.decisions) == 1
        item = result.decisions[0]
        assert item.status == "rejected"
        assert item.evidence == "Client formally rejected the dark wood finish."

    def test_mixed_decisions_and_approvals(self) -> None:
        custom_response = {
            "decisions": [
                {
                    "item_type": "approval",
                    "description": "Approved the architectural drawing",
                    "subject": "architectural drawing",
                    "status": "approved",
                    "evidence": "Client approved the architectural drawing.",
                    "confidence": 0.98,
                },
                {
                    "item_type": "decision",
                    "description": "Proceed with the revised staircase design",
                    "subject": "staircase design",
                    "status": "decided",
                    "evidence": "Let's proceed with the revised staircase design.",
                    "confidence": 0.95,
                },
            ]
        }
        svc = _make_service(fixed_response=custom_response)
        record = _make_record(
            raw_content="Client approved the architectural drawing. Let's proceed with the revised staircase design."
        )
        result = svc.extract_decisions(record)

        assert len(result.decisions) == 2
        types = [d.item_type for d in result.decisions]
        assert "approval" in types
        assert "decision" in types
        assert result.decisions[0].decision_id != result.decisions[1].decision_id

    def test_optional_subject_can_be_none(self) -> None:
        custom_response = {
            "decisions": [
                {
                    "item_type": "decision",
                    "description": "Agreed to proceed",
                    "subject": None,
                    "status": "decided",
                    "evidence": "We agreed to proceed.",
                    "confidence": 0.90,
                }
            ]
        }
        svc = _make_service(fixed_response=custom_response)
        record = _make_record(raw_content="We agreed to proceed.")
        result = svc.extract_decisions(record)

        assert len(result.decisions) == 1
        assert result.decisions[0].subject is None

    def test_with_understanding_context(self) -> None:
        custom_response = {
            "decisions": [
                {
                    "item_type": "approval",
                    "description": "Kitchen layout approved",
                    "subject": "kitchen layout",
                    "status": "approved",
                    "evidence": "Client approved the layout.",
                    "confidence": 0.95,
                }
            ]
        }
        svc = _make_service(fixed_response=custom_response)
        record = _make_record()
        understanding = _make_understanding()
        result = svc.extract_decisions(record, understanding=understanding)

        assert len(result.decisions) == 1

    def test_markdown_code_fences_handled(self) -> None:
        json_text = json.dumps({
            "decisions": [
                {
                    "item_type": "decision",
                    "description": "Use marble flooring",
                    "subject": "flooring",
                    "status": "decided",
                    "evidence": "We decided on marble flooring.",
                    "confidence": 0.94,
                }
            ]
        })
        provider = FakeLLMProvider()
        provider.generate = lambda req: type("LLMResponse", (), {  # type: ignore[assignment]
            "text": f"```json\n{json_text}\n```",
            "model": "fake",
            "usage": {},
        })()
        svc = DecisionService(llm_provider=provider)
        record = _make_record()
        result = svc.extract_decisions(record)

        assert len(result.decisions) == 1
        assert result.decisions[0].description == "Use marble flooring"


# ---------------------------------------------------------------------------
# Non-Decision Cases: Negations, Questions, Suggestions, Actions
# ---------------------------------------------------------------------------


class TestDecisionServiceNonDecisions:
    def test_negated_approval_returns_empty(self) -> None:
        """'The client did not approve the revised layout.' -> []"""
        svc = _make_service(fixed_response={"decisions": []})
        record = _make_record(raw_content="The client did not approve the revised layout.")
        result = svc.extract_decisions(record)

        assert result.decisions == []

    def test_negated_decision_returns_empty(self) -> None:
        """'We haven't decided whether to use granite.' -> []"""
        svc = _make_service(fixed_response={"decisions": []})
        record = _make_record(raw_content="We haven't decided whether to use granite.")
        result = svc.extract_decisions(record)

        assert result.decisions == []

    def test_question_returns_empty(self) -> None:
        """'Has the client approved the layout?' -> []"""
        svc = _make_service(fixed_response={"decisions": []})
        record = _make_record(raw_content="Has the client approved the layout?")
        result = svc.extract_decisions(record)

        assert result.decisions == []

    def test_discussion_alternatives_returns_empty(self) -> None:
        """'Should we use granite or marble?' -> []"""
        svc = _make_service(fixed_response={"decisions": []})
        record = _make_record(raw_content="Should we use granite or marble?")
        result = svc.extract_decisions(record)

        assert result.decisions == []

    def test_suggestion_returns_empty(self) -> None:
        """'I think we should use granite.' -> []"""
        svc = _make_service(fixed_response={"decisions": []})
        record = _make_record(raw_content="I think we should use granite.")
        result = svc.extract_decisions(record)

        assert result.decisions == []

    def test_conditional_hypothetical_returns_empty(self) -> None:
        """'If the client agrees, we will use granite.' -> []"""
        svc = _make_service(fixed_response={"decisions": []})
        record = _make_record(raw_content="If the client agrees, we will use granite.")
        result = svc.extract_decisions(record)

        assert result.decisions == []

    def test_future_possibility_returns_empty(self) -> None:
        """'We may change the staircase design next week.' -> []"""
        svc = _make_service(fixed_response={"decisions": []})
        record = _make_record(raw_content="We may change the staircase design next week.")
        result = svc.extract_decisions(record)

        assert result.decisions == []

    def test_action_only_communication_returns_empty(self) -> None:
        """Pure action item is not a decision or approval."""
        svc = _make_service(fixed_response={"decisions": []})
        record = _make_record(
            raw_content="Architect will send the structural drawing by Friday."
        )
        result = svc.extract_decisions(record)

        assert result.decisions == []


# ---------------------------------------------------------------------------
# Strict Schema Boundaries & Forbidden Field Rejection
# ---------------------------------------------------------------------------


class TestDecisionSchemaBoundaries:
    def test_extra_fields_forbidden_on_extracted_decision_model(self) -> None:
        with pytest.raises(ValidationError):
            ExtractedDecision(
                decision_id="dec-1",
                item_type="decision",
                description="Use granite",
                status="decided",
                evidence="We decided to use granite.",
                confidence=0.9,
                owner="Architect",  # type: ignore[call-arg]
            )

    def test_extra_fields_forbidden_on_payload_model(self) -> None:
        with pytest.raises(ValidationError):
            ExtractedDecisionPayload(
                item_type="decision",
                description="Use granite",
                status="decided",
                evidence="We decided to use granite.",
                confidence=0.9,
                deadline="Friday",  # type: ignore[call-arg]
            )

    def test_llm_returning_owner_fails_validation(self) -> None:
        dirty_response = {
            "decisions": [
                {
                    "item_type": "decision",
                    "description": "Use granite",
                    "status": "decided",
                    "evidence": "We decided to use granite.",
                    "confidence": 0.95,
                    "owner": "Architect",
                }
            ]
        }
        svc = _make_service(fixed_response=dirty_response)
        record = _make_record()
        with pytest.raises(DecisionValidationError, match="failed schema boundary validation"):
            svc.extract_decisions(record)

    def test_llm_returning_responsible_party_fails_validation(self) -> None:
        dirty_response = {
            "decisions": [
                {
                    "item_type": "decision",
                    "description": "Use granite",
                    "status": "decided",
                    "evidence": "We decided to use granite.",
                    "confidence": 0.95,
                    "responsible_party": "Architect",
                }
            ]
        }
        svc = _make_service(fixed_response=dirty_response)
        record = _make_record()
        with pytest.raises(DecisionValidationError, match="failed schema boundary validation"):
            svc.extract_decisions(record)

    def test_llm_returning_deadline_or_due_date_fails_validation(self) -> None:
        dirty_response = {
            "decisions": [
                {
                    "item_type": "decision",
                    "description": "Use granite",
                    "status": "decided",
                    "evidence": "We decided to use granite.",
                    "confidence": 0.95,
                    "deadline": "Friday",
                    "due_date": "2026-10-15",
                }
            ]
        }
        svc = _make_service(fixed_response=dirty_response)
        record = _make_record()
        with pytest.raises(DecisionValidationError, match="failed schema boundary validation"):
            svc.extract_decisions(record)

    def test_llm_returning_task_or_priority_fails_validation(self) -> None:
        dirty_response = {
            "decisions": [
                {
                    "item_type": "decision",
                    "description": "Use granite",
                    "status": "decided",
                    "evidence": "We decided to use granite.",
                    "confidence": 0.95,
                    "task": "Order granite",
                    "priority": "high",
                }
            ]
        }
        svc = _make_service(fixed_response=dirty_response)
        record = _make_record()
        with pytest.raises(DecisionValidationError, match="failed schema boundary validation"):
            svc.extract_decisions(record)

    def test_llm_returning_decision_id_fails_validation(self) -> None:
        """LLM must not generate decision_id; server generates it."""
        dirty_response = {
            "decisions": [
                {
                    "decision_id": "custom-id-123",
                    "item_type": "decision",
                    "description": "Use granite",
                    "status": "decided",
                    "evidence": "We decided to use granite.",
                    "confidence": 0.95,
                }
            ]
        }
        svc = _make_service(fixed_response=dirty_response)
        record = _make_record()
        with pytest.raises(DecisionValidationError, match="failed schema boundary validation"):
            svc.extract_decisions(record)


# ---------------------------------------------------------------------------
# Error Handling & Edge Cases
# ---------------------------------------------------------------------------


class TestDecisionServiceErrors:
    def test_empty_content_raises_decision_error(self) -> None:
        svc = _make_service()
        record = CommunicationRecord.model_construct(
            project_id="proj-villa",
            communication_id="test-comm-001",
            source_type=SourceType.text,
            timestamp=datetime.now(timezone.utc),
            raw_content="   ",
            metadata={},
            storage_path=None,
            status=IngestionStatus.ingested,
        )
        with pytest.raises(DecisionError, match="empty or whitespace-only"):
            svc.extract_decisions(record)

    def test_provider_failure_raises_decision_provider_error(self) -> None:
        svc = _make_service(should_fail=True)
        record = _make_record()
        with pytest.raises(DecisionProviderError, match="simulated provider failure"):
            svc.extract_decisions(record)

    def test_bad_json_raises_decision_validation_error(self) -> None:
        svc = _make_service(bad_json=True)
        record = _make_record()
        with pytest.raises(DecisionValidationError, match="invalid JSON"):
            svc.extract_decisions(record)

    def test_missing_decisions_key_raises_validation_error(self) -> None:
        svc = _make_service(fixed_response={"wrong_key": []})
        record = _make_record()
        with pytest.raises(DecisionValidationError, match="must contain a 'decisions' list"):
            svc.extract_decisions(record)
