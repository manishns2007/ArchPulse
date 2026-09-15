"""
ArchScale — Module 4 Tests
Unit tests for ResponsibilityService.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.llm.base import LLMRequest
from app.llm.provider import FakeLLMProvider
from app.models.action_extraction import ExtractedAction
from app.models.communication import CommunicationRecord, IngestionStatus, SourceType
from app.models.responsibility import (
    ResponsibilityAssignment,
    ResponsibilityAssignmentPayload,
    ResponsibilityExtractionResult,
    VALID_RESPONSIBILITY_TYPES,
)
from app.models.understanding import UnderstandingResult
from app.services.responsibility_service import (
    ResponsibilityError,
    ResponsibilityProviderError,
    ResponsibilityService,
    ResponsibilityValidationError,
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


def _make_service(
    fixed_response: dict | None = None,
    should_fail: bool = False,
    bad_json: bool = False,
) -> ResponsibilityService:
    provider = FakeLLMProvider(
        fixed_response=fixed_response,
        should_fail=should_fail,
        bad_json=bad_json,
    )
    return ResponsibilityService(llm_provider=provider)


# ---------------------------------------------------------------------------
# Success Cases: Responsibility Types & Action Linking
# ---------------------------------------------------------------------------


class TestResponsibilityServiceSuccess:
    def test_explicit_person_responsibility(self) -> None:
        action = _make_action(action_id="act-person", action="Prepare deployment report")
        custom_response = {
            "assignments": [
                {
                    "action_id": "act-person",
                    "responsible_party": "Rahul",
                    "responsibility_type": "person",
                    "evidence": "Rahul will prepare the deployment report.",
                    "confidence": 0.98,
                }
            ]
        }
        svc = _make_service(fixed_response=custom_response)
        record = _make_record(raw_content="Rahul will prepare the deployment report.")
        result = svc.detect_responsibilities(record, actions=[action])

        assert isinstance(result, ResponsibilityExtractionResult)
        assert len(result.assignments) == 1
        assign = result.assignments[0]
        assert assign.action_id == "act-person"
        assert assign.responsible_party == "Rahul"
        assert assign.responsibility_type == "person"
        assert assign.evidence == "Rahul will prepare the deployment report."
        assert assign.confidence == 0.98
        # Server-side generated UUID4
        uuid_obj = UUID(assign.responsibility_id)
        assert uuid_obj.version == 4

    def test_role_based_responsibility(self) -> None:
        action = _make_action(action_id="act-role", action="Send the structural drawing")
        custom_response = {
            "assignments": [
                {
                    "action_id": "act-role",
                    "responsible_party": "Architect",
                    "responsibility_type": "role",
                    "evidence": "The architect will send the structural drawing.",
                    "confidence": 0.95,
                }
            ]
        }
        svc = _make_service(fixed_response=custom_response)
        record = _make_record(raw_content="The architect will send the structural drawing.")
        result = svc.detect_responsibilities(record, actions=[action])

        assert len(result.assignments) == 1
        assign = result.assignments[0]
        assert assign.responsible_party == "Architect"
        assert assign.responsibility_type == "role"

    def test_team_responsibility(self) -> None:
        action = _make_action(action_id="act-team", action="Fix the dashboard")
        custom_response = {
            "assignments": [
                {
                    "action_id": "act-team",
                    "responsible_party": "Frontend team",
                    "responsibility_type": "team",
                    "evidence": "The frontend team needs to fix the dashboard.",
                    "confidence": 0.92,
                }
            ]
        }
        svc = _make_service(fixed_response=custom_response)
        record = _make_record(raw_content="The frontend team needs to fix the dashboard.")
        result = svc.detect_responsibilities(record, actions=[action])

        assert len(result.assignments) == 1
        assign = result.assignments[0]
        assert assign.responsible_party == "Frontend team"
        assert assign.responsibility_type == "team"

    def test_organization_responsibility(self) -> None:
        action = _make_action(action_id="act-org", action="Provide penetration test report")
        custom_response = {
            "assignments": [
                {
                    "action_id": "act-org",
                    "responsible_party": "Acme Security",
                    "responsibility_type": "organization",
                    "evidence": "Acme Security will provide the penetration test report.",
                    "confidence": 0.96,
                }
            ]
        }
        svc = _make_service(fixed_response=custom_response)
        record = _make_record(raw_content="Acme Security will provide the penetration test report.")
        result = svc.detect_responsibilities(record, actions=[action])

        assert len(result.assignments) == 1
        assign = result.assignments[0]
        assert assign.responsible_party == "Acme Security"
        assert assign.responsibility_type == "organization"

    def test_group_responsibility(self) -> None:
        action = _make_action(action_id="act-grp", action="Approve the design revisions")
        custom_response = {
            "assignments": [
                {
                    "action_id": "act-grp",
                    "responsible_party": "Design Review Board",
                    "responsibility_type": "group",
                    "evidence": "The Design Review Board must approve the design revisions.",
                    "confidence": 0.90,
                }
            ]
        }
        svc = _make_service(fixed_response=custom_response)
        record = _make_record(raw_content="The Design Review Board must approve the design revisions.")
        result = svc.detect_responsibilities(record, actions=[action])

        assert len(result.assignments) == 1
        assign = result.assignments[0]
        assert assign.responsible_party == "Design Review Board"
        assert assign.responsibility_type == "group"

    def test_ambiguous_unknown_responsibility(self) -> None:
        action = _make_action(action_id="act-ambig", action="Send revised proposal")
        custom_response = {
            "assignments": [
                {
                    "action_id": "act-ambig",
                    "responsible_party": None,
                    "responsibility_type": "unknown",
                    "evidence": None,
                    "confidence": 0.50,
                }
            ]
        }
        svc = _make_service(fixed_response=custom_response)
        record = _make_record(raw_content="We should send the revised proposal tomorrow.")
        result = svc.detect_responsibilities(record, actions=[action])

        assert len(result.assignments) == 1
        assign = result.assignments[0]
        assert assign.responsible_party is None
        assert assign.responsibility_type == "unknown"
        assert assign.evidence is None

    def test_critical_anti_hallucination_rule(self) -> None:
        # Rahul discussed with Priya, team will send report -> Rahul or Priya must NOT be assigned
        action = _make_action(action_id="act-report", action="Send the report")
        custom_response = {
            "assignments": [
                {
                    "action_id": "act-report",
                    "responsible_party": "The team",
                    "responsibility_type": "team",
                    "evidence": "The team will send the report.",
                    "confidence": 0.91,
                }
            ]
        }
        svc = _make_service(fixed_response=custom_response)
        record = _make_record(
            raw_content="Rahul discussed the deployment with Priya. The team will send the report."
        )
        result = svc.detect_responsibilities(record, actions=[action])

        assert len(result.assignments) == 1
        assign = result.assignments[0]
        assert assign.responsible_party != "Rahul"
        assert assign.responsible_party != "Priya"
        assert assign.responsible_party == "The team"
        assert assign.responsibility_type == "team"

    def test_multiple_actions_linking(self) -> None:
        a1 = _make_action(action_id="act-1", action="Send drawing")
        a2 = _make_action(action_id="act-2", action="Verify dimensions")
        custom_response = {
            "assignments": [
                {
                    "action_id": "act-1",
                    "responsible_party": "Architect",
                    "responsibility_type": "role",
                    "evidence": "Architect will send drawing.",
                    "confidence": 0.95,
                },
                {
                    "action_id": "act-2",
                    "responsible_party": "Contractor",
                    "responsibility_type": "role",
                    "evidence": "Contractor must verify dimensions.",
                    "confidence": 0.88,
                },
            ]
        }
        svc = _make_service(fixed_response=custom_response)
        record = _make_record(raw_content="Architect will send drawing. Contractor must verify dimensions.")
        result = svc.detect_responsibilities(record, actions=[a1, a2])

        assert len(result.assignments) == 2
        assigned_map = {a.action_id: a for a in result.assignments}
        assert assigned_map["act-1"].responsible_party == "Architect"
        assert assigned_map["act-2"].responsible_party == "Contractor"
        assert assigned_map["act-1"].responsibility_id != assigned_map["act-2"].responsibility_id

    def test_empty_actions_returns_empty_assignments_immediately(self) -> None:
        # LLM should fail if called, but service shouldn't call LLM
        svc = _make_service(should_fail=True)
        record = _make_record()
        result = svc.detect_responsibilities(record, actions=[])

        assert isinstance(result, ResponsibilityExtractionResult)
        assert result.assignments == []

    def test_with_understanding_context(self) -> None:
        action = _make_action(action_id="act-ctx")
        custom_response = {
            "assignments": [
                {
                    "action_id": "act-ctx",
                    "responsible_party": "Architect",
                    "responsibility_type": "role",
                    "evidence": "Architect will send drawing.",
                    "confidence": 0.9,
                }
            ]
        }
        svc = _make_service(fixed_response=custom_response)
        record = _make_record()
        understanding = _make_understanding()
        result = svc.detect_responsibilities(record, actions=[action], understanding=understanding)

        assert len(result.assignments) == 1

    def test_markdown_code_fences_parsed(self) -> None:
        action = _make_action(action_id="act-fence")
        json_text = json.dumps({
            "assignments": [
                {
                    "action_id": "act-fence",
                    "responsible_party": "Engineer",
                    "responsibility_type": "role",
                    "evidence": "Engineer will check the beam.",
                    "confidence": 0.92,
                }
            ]
        })
        provider = FakeLLMProvider()
        provider.generate = lambda req: type("LLMResponse", (), {  # type: ignore[assignment]
            "text": f"```json\n{json_text}\n```",
            "model": "fake",
            "usage": {},
        })()
        svc = ResponsibilityService(llm_provider=provider)
        record = _make_record()
        result = svc.detect_responsibilities(record, actions=[action])

        assert len(result.assignments) == 1
        assert result.assignments[0].responsible_party == "Engineer"


# ---------------------------------------------------------------------------
# Strict Schema Boundary & Anti-Leakage Enforcement
# ---------------------------------------------------------------------------


class TestResponsibilitySchemaBoundaries:
    def test_extra_fields_forbidden_on_assignment_model(self) -> None:
        with pytest.raises(ValidationError):
            ResponsibilityAssignment(
                responsibility_id="resp-1",
                action_id="act-1",
                responsible_party="Architect",
                responsibility_type="role",
                evidence="text",
                confidence=0.9,
                deadline="Friday",  # type: ignore[call-arg]
            )

    def test_extra_fields_forbidden_on_payload_model(self) -> None:
        with pytest.raises(ValidationError):
            ResponsibilityAssignmentPayload(
                action_id="act-1",
                responsible_party="Architect",
                responsibility_type="role",
                evidence="text",
                confidence=0.9,
                due_date="2026-10-01",  # type: ignore[call-arg]
            )

    def test_llm_returning_deadline_fails_validation(self) -> None:
        """Module 4 strict boundary: prohibited field 'deadline' from LLM fails validation."""
        action = _make_action(action_id="act-1")
        dirty_response = {
            "assignments": [
                {
                    "action_id": "act-1",
                    "responsible_party": "Architect",
                    "responsibility_type": "role",
                    "evidence": "Architect will send drawing.",
                    "confidence": 0.95,
                    "deadline": "Friday",
                }
            ]
        }
        svc = _make_service(fixed_response=dirty_response)
        record = _make_record()
        with pytest.raises(ResponsibilityValidationError, match="failed schema boundary validation"):
            svc.detect_responsibilities(record, actions=[action])

    def test_llm_returning_decision_or_approval_fails_validation(self) -> None:
        action = _make_action(action_id="act-1")
        dirty_response = {
            "assignments": [
                {
                    "action_id": "act-1",
                    "responsible_party": "Architect",
                    "responsibility_type": "role",
                    "evidence": "Architect will send drawing.",
                    "confidence": 0.95,
                    "decision": "Approved",
                    "approval": True,
                }
            ]
        }
        svc = _make_service(fixed_response=dirty_response)
        record = _make_record()
        with pytest.raises(ResponsibilityValidationError, match="failed schema boundary validation"):
            svc.detect_responsibilities(record, actions=[action])

    def test_llm_returning_priority_or_status_fails_validation(self) -> None:
        action = _make_action(action_id="act-1")
        dirty_response = {
            "assignments": [
                {
                    "action_id": "act-1",
                    "responsible_party": "Architect",
                    "responsibility_type": "role",
                    "evidence": "Architect will send drawing.",
                    "confidence": 0.95,
                    "priority": "high",
                    "status": "in_progress",
                }
            ]
        }
        svc = _make_service(fixed_response=dirty_response)
        record = _make_record()
        with pytest.raises(ResponsibilityValidationError, match="failed schema boundary validation"):
            svc.detect_responsibilities(record, actions=[action])

    def test_llm_returning_owner_fails_validation(self) -> None:
        action = _make_action(action_id="act-1")
        dirty_response = {
            "assignments": [
                {
                    "action_id": "act-1",
                    "responsible_party": "Architect",
                    "responsibility_type": "role",
                    "evidence": "Architect will send drawing.",
                    "confidence": 0.95,
                    "owner": "Architect",
                }
            ]
        }
        svc = _make_service(fixed_response=dirty_response)
        record = _make_record()
        with pytest.raises(ResponsibilityValidationError, match="failed schema boundary validation"):
            svc.detect_responsibilities(record, actions=[action])

    def test_llm_returning_responsibility_id_fails_validation(self) -> None:
        """LLM must not generate responsibility_id; attempting to output it fails validation."""
        action = _make_action(action_id="act-1")
        dirty_response = {
            "assignments": [
                {
                    "responsibility_id": "custom-resp-id",
                    "action_id": "act-1",
                    "responsible_party": "Architect",
                    "responsibility_type": "role",
                    "evidence": "Architect will send drawing.",
                    "confidence": 0.95,
                }
            ]
        }
        svc = _make_service(fixed_response=dirty_response)
        record = _make_record()
        with pytest.raises(ResponsibilityValidationError, match="failed schema boundary validation"):
            svc.detect_responsibilities(record, actions=[action])

    def test_unknown_action_id_fails_validation(self) -> None:
        """If LLM references an action_id that does not exist in Module 3, fail controlled."""
        action = _make_action(action_id="known-act-1")
        hallucinated_response = {
            "assignments": [
                {
                    "action_id": "unknown-act-999",
                    "responsible_party": "Architect",
                    "responsibility_type": "role",
                    "evidence": "Architect will send drawing.",
                    "confidence": 0.95,
                }
            ]
        }
        svc = _make_service(fixed_response=hallucinated_response)
        record = _make_record()
        with pytest.raises(ResponsibilityValidationError, match="references unknown action_id"):
            svc.detect_responsibilities(record, actions=[action])


# ---------------------------------------------------------------------------
# Error Handling & Edge Cases
# ---------------------------------------------------------------------------


class TestResponsibilityServiceErrors:
    def test_empty_content_raises_responsibility_error(self) -> None:
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
        with pytest.raises(ResponsibilityError, match="empty or whitespace-only"):
            svc.detect_responsibilities(record, actions=[action])

    def test_provider_failure_raises_responsibility_provider_error(self) -> None:
        action = _make_action()
        svc = _make_service(should_fail=True)
        record = _make_record()
        with pytest.raises(ResponsibilityProviderError, match="simulated provider failure"):
            svc.detect_responsibilities(record, actions=[action])

    def test_bad_json_raises_responsibility_validation_error(self) -> None:
        action = _make_action()
        svc = _make_service(bad_json=True)
        record = _make_record()
        with pytest.raises(ResponsibilityValidationError, match="invalid JSON"):
            svc.detect_responsibilities(record, actions=[action])

    def test_missing_assignments_key_raises_validation_error(self) -> None:
        action = _make_action()
        svc = _make_service(fixed_response={"wrong_key": []})
        record = _make_record()
        with pytest.raises(ResponsibilityValidationError, match="must contain an 'assignments' list"):
            svc.detect_responsibilities(record, actions=[action])
