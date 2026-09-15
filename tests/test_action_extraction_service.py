"""
ArchScale — Module 3 Tests
Unit tests for ActionExtractionService.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.llm.base import LLMRequest
from app.llm.provider import FakeLLMProvider
from app.models.action_extraction import (
    ActionExtractionResult,
    ExtractedAction,
    VALID_ACTION_TYPES,
)
from app.models.communication import CommunicationRecord, IngestionStatus, SourceType
from app.models.understanding import UnderstandingResult
from app.services.action_extraction_service import (
    ActionExtractionError,
    ActionExtractionProviderError,
    ActionExtractionService,
    ActionExtractionValidationError,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_record(
    raw_content: str = "Architect will send the structural drawing by Friday.",
    project_id: str = "proj-villa",
    communication_id: str = "test-comm-001",
    source_type: SourceType = SourceType.text,
) -> CommunicationRecord:
    return CommunicationRecord(
        project_id=project_id,
        communication_id=communication_id,
        source_type=source_type,
        timestamp=datetime.now(timezone.utc),
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
        concise_summary="Architect will send structural drawings.",
        detailed_summary="Architect will send structural drawings by Friday for client review.",
        topics=["structural drawing", "review"],
        stakeholders=["Architect", "Client"],
        communication_type="update",
        important_context=["Drawing needed before Friday."],
    )


def _make_service(
    fixed_response: dict | None = None,
    should_fail: bool = False,
    bad_json: bool = False,
) -> ActionExtractionService:
    provider = FakeLLMProvider(
        fixed_response=fixed_response,
        should_fail=should_fail,
        bad_json=bad_json,
    )
    return ActionExtractionService(llm_provider=provider)


# ---------------------------------------------------------------------------
# Success Cases
# ---------------------------------------------------------------------------


class TestActionExtractionServiceSuccess:
    def test_extract_actions_returns_valid_result(self) -> None:
        svc = _make_service()
        record = _make_record()
        result = svc.extract_actions(record)

        assert isinstance(result, ActionExtractionResult)
        assert result.project_id == record.project_id
        assert result.communication_id == record.communication_id
        assert len(result.actions) > 0
        assert result.llm_model == "fake"
        assert isinstance(result.extracted_at, datetime)

    def test_action_id_is_valid_uuid_generated_server_side(self) -> None:
        svc = _make_service()
        record = _make_record()
        result = svc.extract_actions(record)

        for action in result.actions:
            assert action.action_id is not None
            # Validate it is a valid UUID
            uuid_obj = UUID(action.action_id)
            assert uuid_obj.version == 4

    def test_multiple_actions_extraction(self) -> None:
        custom_response = {
            "actions": [
                {
                    "action": "Update structural drawing",
                    "evidence": "Architect will update the structural drawing.",
                    "confidence": 0.95,
                    "action_type": "deliverable",
                },
                {
                    "action": "Verify cabinet dimensions",
                    "evidence": "Contractor should verify the cabinet dimensions.",
                    "confidence": 0.90,
                    "action_type": "task",
                },
                {
                    "action": "Review the updated plan",
                    "evidence": "The client will review the updated plan.",
                    "confidence": 0.85,
                    "action_type": "review",
                },
            ]
        }
        svc = _make_service(fixed_response=custom_response)
        record = _make_record(
            raw_content=(
                "Architect will update the structural drawing. "
                "Contractor should verify the cabinet dimensions. "
                "The client will review the updated plan."
            )
        )
        result = svc.extract_actions(record)

        assert len(result.actions) == 3
        actions_text = [a.action for a in result.actions]
        assert "Update structural drawing" in actions_text
        assert "Verify cabinet dimensions" in actions_text
        assert "Review the updated plan" in actions_text

        # Every action must have its own unique UUID4
        ids = [a.action_id for a in result.actions]
        assert len(set(ids)) == 3

    def test_non_actionable_returns_empty_actions(self) -> None:
        custom_response = {"actions": []}
        svc = _make_service(fixed_response=custom_response)
        record = _make_record(raw_content="The team discussed the revised kitchen layout.")
        result = svc.extract_actions(record)

        assert isinstance(result, ActionExtractionResult)
        assert result.actions == []

    def test_with_understanding_context(self) -> None:
        svc = _make_service()
        record = _make_record()
        understanding = _make_understanding()
        result = svc.extract_actions(record, understanding=understanding)

        assert isinstance(result, ActionExtractionResult)
        assert len(result.actions) > 0

    def test_markdown_code_fences_handled(self) -> None:
        json_content = json.dumps({
            "actions": [
                {
                    "action": "Submit permit application",
                    "evidence": "Please submit the permit application.",
                    "confidence": 0.9,
                    "action_type": "task",
                }
            ]
        })
        provider = FakeLLMProvider()
        # Mock raw text with markdown fences
        provider.generate = lambda req: type("LLMResponse", (), {  # type: ignore[assignment]
            "text": f"```json\n{json_content}\n```",
            "model": "fake",
            "usage": {},
        })()
        svc = ActionExtractionService(llm_provider=provider)
        record = _make_record()
        result = svc.extract_actions(record)

        assert len(result.actions) == 1
        assert result.actions[0].action == "Submit permit application"


# ---------------------------------------------------------------------------
# Strict Negative Constraints / Boundary Enforcement
# ---------------------------------------------------------------------------


class TestActionExtractionBoundaries:
    def test_no_prohibited_fields_on_extracted_action(self) -> None:
        action = ExtractedAction(
            action="Test action",
            evidence="Evidence text",
            confidence=0.9,
            action_type="task",
        )
        data = action.model_dump()
        prohibited = ["owner", "responsible_person", "deadline", "due_date", "decision", "approval"]
        for p in prohibited:
            assert p not in data

    def test_extra_fields_forbidden_on_extracted_action(self) -> None:
        with pytest.raises(ValidationError):
            ExtractedAction(
                action="Test action",
                evidence="Evidence text",
                confidence=0.9,
                action_type="task",
                owner="Architect",  # type: ignore[call-arg]
            )

    def test_service_defensively_strips_prohibited_fields_from_llm(self) -> None:
        """If the LLM returns owner/deadline keys, service strips them without failing."""
        dirty_response = {
            "actions": [
                {
                    "action": "Send structural drawing",
                    "evidence": "Architect will send structural drawing by Friday.",
                    "confidence": 0.95,
                    "action_type": "deliverable",
                    "owner": "Architect",
                    "deadline": "Friday",
                    "decision": "Approved earlier",
                }
            ]
        }
        svc = _make_service(fixed_response=dirty_response)
        record = _make_record()
        result = svc.extract_actions(record)

        assert len(result.actions) == 1
        action = result.actions[0]
        assert action.action == "Send structural drawing"
        # Prohibited fields must not exist
        dumped = action.model_dump()
        assert "owner" not in dumped
        assert "deadline" not in dumped
        assert "decision" not in dumped


# ---------------------------------------------------------------------------
# Action Types & Validation
# ---------------------------------------------------------------------------


class TestActionTypes:
    @pytest.mark.parametrize("action_type", list(VALID_ACTION_TYPES))
    def test_all_valid_action_types_accepted(self, action_type: str) -> None:
        action = ExtractedAction(
            action="Action item",
            evidence="Source quote",
            confidence=0.8,
            action_type=action_type,
        )
        assert action.action_type == action_type

    def test_invalid_action_type_falls_back_to_other(self) -> None:
        action = ExtractedAction(
            action="Action item",
            evidence="Source quote",
            confidence=0.8,
            action_type="unknown_custom_type",
        )
        assert action.action_type == "other"

    def test_confidence_out_of_bounds_raises_validation_error(self) -> None:
        with pytest.raises(ValidationError):
            ExtractedAction(
                action="Action item",
                evidence="Source quote",
                confidence=1.5,
                action_type="task",
            )
        with pytest.raises(ValidationError):
            ExtractedAction(
                action="Action item",
                evidence="Source quote",
                confidence=-0.1,
                action_type="task",
            )


# ---------------------------------------------------------------------------
# Error Handling
# ---------------------------------------------------------------------------


class TestActionExtractionServiceErrors:
    def test_empty_raw_content_raises_error(self) -> None:
        svc = _make_service()
        record = CommunicationRecord.model_construct(
            project_id="proj-1",
            communication_id="comm-1",
            source_type=SourceType.text,
            timestamp=datetime.now(timezone.utc),
            raw_content="   ",
            metadata={},
            storage_path=None,
            status=IngestionStatus.ingested,
        )
        with pytest.raises(ActionExtractionError, match="empty or whitespace"):
            svc.extract_actions(record)

    def test_provider_failure_raises_provider_error(self) -> None:
        svc = _make_service(should_fail=True)
        record = _make_record()
        with pytest.raises(ActionExtractionProviderError, match="failed"):
            svc.extract_actions(record)

    def test_bad_json_raises_validation_error(self) -> None:
        svc = _make_service(bad_json=True)
        record = _make_record()
        with pytest.raises(ActionExtractionValidationError, match="invalid JSON"):
            svc.extract_actions(record)

    def test_missing_actions_key_raises_validation_error(self) -> None:
        svc = _make_service(fixed_response={"summary": "wrong schema"})
        record = _make_record()
        with pytest.raises(ActionExtractionValidationError, match="must contain an 'actions' list"):
            svc.extract_actions(record)

    def test_actions_not_a_list_raises_validation_error(self) -> None:
        svc = _make_service(fixed_response={"actions": "not-a-list"})
        record = _make_record()
        with pytest.raises(ActionExtractionValidationError, match="must contain an 'actions' list"):
            svc.extract_actions(record)

    def test_action_item_invalid_raises_validation_error(self) -> None:
        svc = _make_service(fixed_response={"actions": ["not a dict"]})
        record = _make_record()
        with pytest.raises(ActionExtractionValidationError, match="not a valid JSON object"):
            svc.extract_actions(record)
