"""
ArchScale — Module 5 Tests
Unit tests for DeadlineService.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.llm.provider import FakeLLMProvider
from app.models.action_extraction import ExtractedAction
from app.models.communication import CommunicationRecord, IngestionStatus, SourceType
from app.models.deadline import (
    DeadlineAssignment,
    DeadlineAssignmentPayload,
    DeadlineExtractionResult,
    VALID_DEADLINE_TYPES,
)
from app.models.responsibility import ResponsibilityAssignment
from app.models.understanding import UnderstandingResult
from app.services.deadline_service import (
    DeadlineError,
    DeadlineProviderError,
    DeadlineService,
    DeadlineValidationError,
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
        timestamp=datetime(2026, 9, 14, 10, 0, tzinfo=timezone.utc),
        raw_content=raw_content,
        metadata={"char_count": len(raw_content)},
        storage_path=None,
        status=IngestionStatus.ingested,
    )


def _make_action(
    action_id: str = "action-001",
    action: str = "Send structural drawing",
    evidence: str = "Architect will send the structural drawing by Friday.",
    action_type: str = "deliverable",
) -> ExtractedAction:
    return ExtractedAction(
        action_id=action_id,
        action=action,
        evidence=evidence,
        confidence=0.95,
        action_type=action_type,
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


def _make_responsibility(
    action_id: str = "action-001",
    responsible_party: str = "Architect",
    responsibility_type: str = "role",
) -> ResponsibilityAssignment:
    return ResponsibilityAssignment(
        responsibility_id="resp-001",
        action_id=action_id,
        responsible_party=responsible_party,
        responsibility_type=responsibility_type,  # type: ignore[arg-type]
        evidence="Architect will send the structural drawing by Friday.",
        confidence=0.95,
    )


def _make_service(
    fixed_response: dict | None = None,
    should_fail: bool = False,
    bad_json: bool = False,
) -> DeadlineService:
    provider = FakeLLMProvider(
        fixed_response=fixed_response,
        should_fail=should_fail,
        bad_json=bad_json,
    )
    return DeadlineService(llm_provider=provider)


# ---------------------------------------------------------------------------
# Success Cases: Deadline Types & Action Linking
# ---------------------------------------------------------------------------


class TestDeadlineServiceSuccess:
    def test_relative_day_deadline(self) -> None:
        action = _make_action(action_id="act-rel-day", action="Finalize staircase design")
        custom_response = {
            "assignments": [
                {
                    "action_id": "act-rel-day",
                    "deadline": "Friday",
                    "deadline_type": "relative_day",
                    "normalized_deadline": None,
                    "evidence": "Britto Sir will finalize the staircase design by Friday.",
                    "confidence": 0.95,
                }
            ]
        }
        svc = _make_service(fixed_response=custom_response)
        record = _make_record(
            raw_content="Britto Sir will finalize the staircase design by Friday."
        )
        result = svc.detect_deadlines(record, actions=[action])

        assert isinstance(result, DeadlineExtractionResult)
        assert len(result.assignments) == 1
        assign = result.assignments[0]
        assert assign.action_id == "act-rel-day"
        assert assign.deadline == "Friday"
        assert assign.deadline_type == "relative_day"
        assert assign.normalized_deadline is None
        assert assign.evidence == "Britto Sir will finalize the staircase design by Friday."
        assert assign.confidence == 0.95
        # Validate UUID4
        uuid_obj = UUID(assign.deadline_id)
        assert uuid_obj.version == 4

    def test_exact_date_deadline(self) -> None:
        action = _make_action(action_id="act-exact", action="Submit permit application")
        custom_response = {
            "assignments": [
                {
                    "action_id": "act-exact",
                    "deadline": "October 15, 2026",
                    "deadline_type": "exact_date",
                    "normalized_deadline": "2026-10-15",
                    "evidence": "Submit the permit application by October 15, 2026.",
                    "confidence": 0.98,
                }
            ]
        }
        svc = _make_service(fixed_response=custom_response)
        record = _make_record(
            raw_content="Submit the permit application by October 15, 2026."
        )
        result = svc.detect_deadlines(record, actions=[action])

        assert len(result.assignments) == 1
        assign = result.assignments[0]
        assert assign.deadline == "October 15, 2026"
        assert assign.deadline_type == "exact_date"
        assert assign.normalized_deadline == "2026-10-15"

    def test_relative_time_deadline(self) -> None:
        action = _make_action(action_id="act-rel-time", action="Submit revision")
        custom_response = {
            "assignments": [
                {
                    "action_id": "act-rel-time",
                    "deadline": "by 5 PM",
                    "deadline_type": "relative_time",
                    "normalized_deadline": None,
                    "evidence": "Submit revision by 5 PM today.",
                    "confidence": 0.92,
                }
            ]
        }
        svc = _make_service(fixed_response=custom_response)
        record = _make_record(raw_content="Submit revision by 5 PM today.")
        result = svc.detect_deadlines(record, actions=[action])

        assert len(result.assignments) == 1
        assign = result.assignments[0]
        assert assign.deadline == "by 5 PM"
        assert assign.deadline_type == "relative_time"

    def test_event_based_deadline(self) -> None:
        action = _make_action(action_id="act-event", action="Check the reinforcement")
        custom_response = {
            "assignments": [
                {
                    "action_id": "act-event",
                    "deadline": "prior to concrete pouring",
                    "deadline_type": "event_based",
                    "normalized_deadline": None,
                    "evidence": "Check the reinforcement prior to concrete pouring.",
                    "confidence": 0.94,
                }
            ]
        }
        svc = _make_service(fixed_response=custom_response)
        record = _make_record(
            raw_content="Check the reinforcement prior to concrete pouring."
        )
        result = svc.detect_deadlines(record, actions=[action])

        assert len(result.assignments) == 1
        assign = result.assignments[0]
        assert assign.deadline == "prior to concrete pouring"
        assert assign.deadline_type == "event_based"

    def test_no_deadline_assignment(self) -> None:
        action = _make_action(action_id="act-none", action="Review the kitchen layout")
        custom_response = {
            "assignments": [
                {
                    "action_id": "act-none",
                    "deadline": None,
                    "deadline_type": "no_deadline",
                    "normalized_deadline": None,
                    "evidence": None,
                    "confidence": 1.0,
                }
            ]
        }
        svc = _make_service(fixed_response=custom_response)
        record = _make_record(raw_content="We should review the kitchen layout.")
        result = svc.detect_deadlines(record, actions=[action])

        assert len(result.assignments) == 1
        assign = result.assignments[0]
        assert assign.deadline is None
        assert assign.deadline_type == "no_deadline"
        assert assign.normalized_deadline is None
        assert assign.evidence is None
        assert assign.confidence == 1.0

    def test_ambiguous_unknown_deadline(self) -> None:
        action = _make_action(action_id="act-unk", action="Send the specs")
        custom_response = {
            "assignments": [
                {
                    "action_id": "act-unk",
                    "deadline": "sometime soon",
                    "deadline_type": "unknown",
                    "normalized_deadline": None,
                    "evidence": "We need the specs sometime soon.",
                    "confidence": 0.5,
                }
            ]
        }
        svc = _make_service(fixed_response=custom_response)
        record = _make_record(raw_content="We need the specs sometime soon.")
        result = svc.detect_deadlines(record, actions=[action])

        assert len(result.assignments) == 1
        assign = result.assignments[0]
        assert assign.deadline == "sometime soon"
        assert assign.deadline_type == "unknown"

    def test_ordinary_date_vs_actual_deadline(self) -> None:
        """
        Meeting on Monday is a past/discussion date, NOT a deadline.
        Friday is the actual deadline for finalizing design.
        """
        action = _make_action(action_id="act-design", action="Finalize the design")
        custom_response = {
            "assignments": [
                {
                    "action_id": "act-design",
                    "deadline": "Friday",
                    "deadline_type": "relative_day",
                    "normalized_deadline": None,
                    "evidence": "Britto will finalize the design by Friday.",
                    "confidence": 0.95,
                }
            ]
        }
        svc = _make_service(fixed_response=custom_response)
        record = _make_record(
            raw_content="We met on Monday and discussed the staircase. Britto will finalize the design by Friday."
        )
        result = svc.detect_deadlines(record, actions=[action])

        assert len(result.assignments) == 1
        assign = result.assignments[0]
        assert assign.deadline == "Friday"
        assert assign.deadline != "Monday"

    def test_past_event_date_is_not_deadline(self) -> None:
        """Client approved on Sept 10 is an event date, not an action deadline."""
        action = _make_action(action_id="act-layout", action="Review the approved design")
        custom_response = {
            "assignments": [
                {
                    "action_id": "act-layout",
                    "deadline": None,
                    "deadline_type": "no_deadline",
                    "normalized_deadline": None,
                    "evidence": None,
                    "confidence": 1.0,
                }
            ]
        }
        svc = _make_service(fixed_response=custom_response)
        record = _make_record(
            raw_content="The client approved the design on September 10. Review the approved design."
        )
        result = svc.detect_deadlines(record, actions=[action])

        assert len(result.assignments) == 1
        assign = result.assignments[0]
        assert assign.deadline is None
        assert assign.deadline_type == "no_deadline"

    def test_multiple_actions_with_different_deadlines(self) -> None:
        a1 = _make_action(action_id="act-1", action="Send drawings")
        a2 = _make_action(action_id="act-2", action="Verify dimensions")
        custom_response = {
            "assignments": [
                {
                    "action_id": "act-1",
                    "deadline": "Friday",
                    "deadline_type": "relative_day",
                    "normalized_deadline": None,
                    "evidence": "Send drawings by Friday.",
                    "confidence": 0.95,
                },
                {
                    "action_id": "act-2",
                    "deadline": None,
                    "deadline_type": "no_deadline",
                    "normalized_deadline": None,
                    "evidence": None,
                    "confidence": 1.0,
                },
            ]
        }
        svc = _make_service(fixed_response=custom_response)
        record = _make_record(
            raw_content="Send drawings by Friday. Contractor should verify dimensions."
        )
        result = svc.detect_deadlines(record, actions=[a1, a2])

        assert len(result.assignments) == 2
        assign_map = {a.action_id: a for a in result.assignments}
        assert assign_map["act-1"].deadline == "Friday"
        assert assign_map["act-1"].deadline_type == "relative_day"
        assert assign_map["act-2"].deadline is None
        assert assign_map["act-2"].deadline_type == "no_deadline"

    def test_deterministic_fallback_for_omitted_action(self) -> None:
        """If LLM omits an action, service attaches a deterministic no_deadline assignment."""
        a1 = _make_action(action_id="act-1")
        a2 = _make_action(action_id="act-2")
        # LLM only returns assignment for act-1
        custom_response = {
            "assignments": [
                {
                    "action_id": "act-1",
                    "deadline": "Friday",
                    "deadline_type": "relative_day",
                    "normalized_deadline": None,
                    "evidence": "Send drawings by Friday.",
                    "confidence": 0.95,
                }
            ]
        }
        svc = _make_service(fixed_response=custom_response)
        record = _make_record()
        result = svc.detect_deadlines(record, actions=[a1, a2])

        assert len(result.assignments) == 2
        assign_map = {a.action_id: a for a in result.assignments}
        assert assign_map["act-1"].deadline == "Friday"
        assert assign_map["act-2"].action_id == "act-2"
        assert assign_map["act-2"].deadline is None
        assert assign_map["act-2"].deadline_type == "no_deadline"
        assert assign_map["act-2"].confidence == 1.0

    def test_empty_actions_returns_empty_assignments_immediately(self) -> None:
        svc = _make_service(should_fail=True)
        record = _make_record()
        result = svc.detect_deadlines(record, actions=[])

        assert isinstance(result, DeadlineExtractionResult)
        assert result.assignments == []

    def test_with_understanding_and_responsibility_context(self) -> None:
        action = _make_action(action_id="act-ctx")
        custom_response = {
            "assignments": [
                {
                    "action_id": "act-ctx",
                    "deadline": "Friday",
                    "deadline_type": "relative_day",
                    "normalized_deadline": None,
                    "evidence": "Send drawing by Friday.",
                    "confidence": 0.95,
                }
            ]
        }
        svc = _make_service(fixed_response=custom_response)
        record = _make_record()
        understanding = _make_understanding()
        responsibility = _make_responsibility(action_id="act-ctx")

        result = svc.detect_deadlines(
            record,
            actions=[action],
            understanding=understanding,
            responsibilities=[responsibility],
        )
        assert len(result.assignments) == 1

    def test_markdown_code_fences_handled(self) -> None:
        action = _make_action(action_id="act-fence")
        json_text = json.dumps({
            "assignments": [
                {
                    "action_id": "act-fence",
                    "deadline": "tomorrow",
                    "deadline_type": "relative_day",
                    "normalized_deadline": None,
                    "evidence": "Send it tomorrow.",
                    "confidence": 0.90,
                }
            ]
        })
        provider = FakeLLMProvider()
        provider.generate = lambda req: type("LLMResponse", (), {  # type: ignore[assignment]
            "text": f"```json\n{json_text}\n```",
            "model": "fake",
            "usage": {},
        })()
        svc = DeadlineService(llm_provider=provider)
        record = _make_record()
        result = svc.detect_deadlines(record, actions=[action])

        assert len(result.assignments) == 1
        assert result.assignments[0].deadline == "tomorrow"


# ---------------------------------------------------------------------------
# Strict Schema Boundaries & Forbidden Field Rejection
# ---------------------------------------------------------------------------


class TestDeadlineSchemaBoundaries:
    def test_extra_fields_forbidden_on_assignment_model(self) -> None:
        with pytest.raises(ValidationError):
            DeadlineAssignment(
                deadline_id="dl-1",
                action_id="act-1",
                deadline="Friday",
                deadline_type="relative_day",
                confidence=0.9,
                owner="Architect",  # type: ignore[call-arg]
            )

    def test_extra_fields_forbidden_on_payload_model(self) -> None:
        with pytest.raises(ValidationError):
            DeadlineAssignmentPayload(
                action_id="act-1",
                deadline="Friday",
                deadline_type="relative_day",
                confidence=0.9,
                responsible_party="Architect",  # type: ignore[call-arg]
            )

    def test_llm_returning_owner_fails_validation(self) -> None:
        action = _make_action(action_id="act-1")
        dirty_response = {
            "assignments": [
                {
                    "action_id": "act-1",
                    "deadline": "Friday",
                    "deadline_type": "relative_day",
                    "confidence": 0.95,
                    "owner": "Architect",
                }
            ]
        }
        svc = _make_service(fixed_response=dirty_response)
        record = _make_record()
        with pytest.raises(DeadlineValidationError, match="failed schema boundary validation"):
            svc.detect_deadlines(record, actions=[action])

    def test_llm_returning_responsible_party_fails_validation(self) -> None:
        action = _make_action(action_id="act-1")
        dirty_response = {
            "assignments": [
                {
                    "action_id": "act-1",
                    "deadline": "Friday",
                    "deadline_type": "relative_day",
                    "confidence": 0.95,
                    "responsible_party": "Architect",
                }
            ]
        }
        svc = _make_service(fixed_response=dirty_response)
        record = _make_record()
        with pytest.raises(DeadlineValidationError, match="failed schema boundary validation"):
            svc.detect_deadlines(record, actions=[action])

    def test_llm_returning_decision_or_approval_fails_validation(self) -> None:
        action = _make_action(action_id="act-1")
        dirty_response = {
            "assignments": [
                {
                    "action_id": "act-1",
                    "deadline": "Friday",
                    "deadline_type": "relative_day",
                    "confidence": 0.95,
                    "decision": "Approved",
                    "approval": True,
                }
            ]
        }
        svc = _make_service(fixed_response=dirty_response)
        record = _make_record()
        with pytest.raises(DeadlineValidationError, match="failed schema boundary validation"):
            svc.detect_deadlines(record, actions=[action])

    def test_llm_returning_priority_or_status_fails_validation(self) -> None:
        action = _make_action(action_id="act-1")
        dirty_response = {
            "assignments": [
                {
                    "action_id": "act-1",
                    "deadline": "Friday",
                    "deadline_type": "relative_day",
                    "confidence": 0.95,
                    "priority": "high",
                    "status": "pending",
                }
            ]
        }
        svc = _make_service(fixed_response=dirty_response)
        record = _make_record()
        with pytest.raises(DeadlineValidationError, match="failed schema boundary validation"):
            svc.detect_deadlines(record, actions=[action])

    def test_llm_returning_deadline_id_fails_validation(self) -> None:
        """LLM must not generate deadline_id; server generates it."""
        action = _make_action(action_id="act-1")
        dirty_response = {
            "assignments": [
                {
                    "deadline_id": "custom-id-123",
                    "action_id": "act-1",
                    "deadline": "Friday",
                    "deadline_type": "relative_day",
                    "confidence": 0.95,
                }
            ]
        }
        svc = _make_service(fixed_response=dirty_response)
        record = _make_record()
        with pytest.raises(DeadlineValidationError, match="failed schema boundary validation"):
            svc.detect_deadlines(record, actions=[action])

    def test_unknown_action_id_fails_validation(self) -> None:
        """If LLM outputs an action_id not present in Module 3, fail controlled."""
        action = _make_action(action_id="known-act-1")
        hallucinated_response = {
            "assignments": [
                {
                    "action_id": "unknown-act-999",
                    "deadline": "Friday",
                    "deadline_type": "relative_day",
                    "confidence": 0.95,
                }
            ]
        }
        svc = _make_service(fixed_response=hallucinated_response)
        record = _make_record()
        with pytest.raises(DeadlineValidationError, match="references unknown action_id"):
            svc.detect_deadlines(record, actions=[action])


# ---------------------------------------------------------------------------
# Error Handling & Edge Cases
# ---------------------------------------------------------------------------


class TestDeadlineServiceErrors:
    def test_empty_content_raises_deadline_error(self) -> None:
        action = _make_action()
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
        with pytest.raises(DeadlineError, match="empty or whitespace-only"):
            svc.detect_deadlines(record, actions=[action])

    def test_provider_failure_raises_deadline_provider_error(self) -> None:
        action = _make_action()
        svc = _make_service(should_fail=True)
        record = _make_record()
        with pytest.raises(DeadlineProviderError, match="simulated provider failure"):
            svc.detect_deadlines(record, actions=[action])

    def test_bad_json_raises_deadline_validation_error(self) -> None:
        action = _make_action()
        svc = _make_service(bad_json=True)
        record = _make_record()
        with pytest.raises(DeadlineValidationError, match="invalid JSON"):
            svc.detect_deadlines(record, actions=[action])

    def test_missing_assignments_key_raises_validation_error(self) -> None:
        action = _make_action()
        svc = _make_service(fixed_response={"wrong_key": []})
        record = _make_record()
        with pytest.raises(DeadlineValidationError, match="must contain an 'assignments' list"):
            svc.detect_deadlines(record, actions=[action])
