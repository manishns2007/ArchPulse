"""
ArchScale — Module 7 Tests
Unit tests for TaskService (app/services/task_service.py).
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from app.models.action_extraction import (
    ActionExtractionResult,
    ExtractedAction,
)
from app.models.communication import CommunicationRecord, IngestionStatus, SourceType
from app.models.deadline import (
    DeadlineAssignment,
    DeadlineExtractionResult,
)
from app.models.decision import (
    DecisionExtractionResult,
    ExtractedDecision,
)
from app.models.responsibility import (
    ResponsibilityAssignment,
    ResponsibilityExtractionResult,
)
from app.models.task import (
    StructuredTask,
    StructuredTaskResult,
)
from app.models.understanding import UnderstandingResult
from app.services.task_service import (
    TaskError,
    TaskService,
    TaskValidationError,
)


# ---------------------------------------------------------------------------
# Helpers & Fixtures
# ---------------------------------------------------------------------------


def _make_record(
    raw_content: str = (
        "Client approved the revised kitchen layout. "
        "Architect will send the structural drawing by Friday. "
        "Britto Sir will review the drawing after it is received."
    ),
    project_id: str = "proj-villa",
    communication_id: str = "test-comm-001",
) -> CommunicationRecord:
    return CommunicationRecord(
        project_id=project_id,
        communication_id=communication_id,
        source_type=SourceType.text,
        timestamp=datetime(2026, 9, 14, 10, 0, tzinfo=timezone.utc),
        raw_content=raw_content,
        metadata={"char_count": len(raw_content)},
        storage_path=None,
        status=IngestionStatus.ingested,
    )


def _make_action(
    action_id: str | UUID,
    action: str = "Send structural drawing",
    evidence: str = "Architect will send the structural drawing by Friday.",
    confidence: float = 0.9,
) -> ExtractedAction:
    return ExtractedAction(
        action_id=str(action_id),
        action=action,
        evidence=evidence,
        confidence=confidence,
    )


def _make_responsibility(
    action_id: str | UUID,
    responsible_party: str | None = "Architect",
    responsibility_type: str | None = "role",
    evidence: str = "Architect will send the structural drawing by Friday.",
    confidence: float = 0.9,
) -> ResponsibilityAssignment:
    return ResponsibilityAssignment(
        responsibility_id=str(uuid4()),
        action_id=str(action_id),
        responsible_party=responsible_party,
        responsibility_type=responsibility_type,  # type: ignore[arg-type]
        evidence=evidence,
        confidence=confidence,
    )


def _make_deadline(
    action_id: str | UUID,
    deadline: str | None = "Friday",
    deadline_type: str = "relative_day",
    normalized_deadline: str | None = "2026-09-18",
    evidence: str = "by Friday",
    confidence: float = 0.9,
) -> DeadlineAssignment:
    return DeadlineAssignment(
        deadline_id=str(uuid4()),
        action_id=str(action_id),
        deadline=deadline,
        deadline_type=deadline_type,  # type: ignore[arg-type]
        normalized_deadline=normalized_deadline,
        evidence=evidence,
        confidence=confidence,
    )


def _make_decision(
    description: str = "Revised kitchen layout was approved by the client.",
    item_type: str = "approval",
    status: str = "approved",
    evidence: str = "Client approved the revised kitchen layout.",
    confidence: float = 0.95,
) -> ExtractedDecision:
    return ExtractedDecision(
        decision_id=str(uuid4()),
        description=description,
        item_type=item_type,  # type: ignore[arg-type]
        status=status,  # type: ignore[arg-type]
        evidence=evidence,
        confidence=confidence,
    )


# ---------------------------------------------------------------------------
# Test Cases
# ---------------------------------------------------------------------------


class TestTaskService:
    @pytest.fixture
    def service(self) -> TaskService:
        return TaskService()

    def test_empty_actions_returns_empty_task_result(self, service: TaskService) -> None:
        record = _make_record()
        result = service.create_structured_tasks(
            record=record,
            actions=[],
        )
        assert isinstance(result, StructuredTaskResult)
        assert result.tasks == []
        assert result.task_count == 0
        assert result.project_id == "proj-villa"
        assert result.communication_id == "test-comm-001"

    def test_empty_raw_content_raises_task_error(self, service: TaskService) -> None:
        record = _make_record()
        object.__setattr__(record, "raw_content", "   ")
        with pytest.raises(TaskError, match="empty or whitespace-only"):
            service.create_structured_tasks(record=record, actions=[])

    def test_basic_single_action_to_single_task(self, service: TaskService) -> None:
        record = _make_record()
        action_id = "act-001"
        action = _make_action(action_id, "Send the structural drawing", "Architect will send the structural drawing by Friday.")
        resp = _make_responsibility(action_id, "Architect", "role")
        dl = _make_deadline(action_id, "Friday", "relative_day", "2026-09-18")
        dec = _make_decision()

        result = service.create_structured_tasks(
            record=record,
            actions=[action],
            responsibilities=[resp],
            deadlines=[dl],
            decisions=[dec],
        )

        assert result.task_count == 1
        assert len(result.tasks) == 1
        task = result.tasks[0]
        assert task.title == "Send the structural drawing"
        assert task.action_id == action_id
        assert task.responsible_party == "Architect"
        assert task.responsibility_type == "role"
        assert task.deadline == "Friday"
        assert task.deadline_type == "relative_day"
        assert task.normalized_deadline == "2026-09-18"
        assert task.status == "pending"
        assert task.priority == "unspecified"
        assert "Client approved the revised kitchen layout." in task.decision_context
        assert isinstance(task.task_id, UUID)
        assert task.task_id.version == 4

    def test_missing_responsibility_defaults_to_none(self, service: TaskService) -> None:
        record = _make_record()
        action_id = "act-002"
        action = _make_action(action_id, "Check site conditions")

        result = service.create_structured_tasks(
            record=record,
            actions=[action],
            responsibilities=[],
        )

        assert len(result.tasks) == 1
        task = result.tasks[0]
        assert task.responsible_party is None
        assert task.responsibility_type is None

    def test_missing_deadline_defaults_to_no_deadline(self, service: TaskService) -> None:
        record = _make_record()
        action_id = "act-003"
        action = _make_action(action_id, "Review blueprints")

        result = service.create_structured_tasks(
            record=record,
            actions=[action],
            deadlines=[],
        )

        assert len(result.tasks) == 1
        task = result.tasks[0]
        assert task.deadline is None
        assert task.deadline_type == "no_deadline"
        assert task.normalized_deadline is None

    def test_decision_only_communication_returns_empty_tasks(self, service: TaskService) -> None:
        record = _make_record(raw_content="Client approved the kitchen countertop material.")
        dec = _make_decision("Countertop approved", "approval", "approved", "Client approved the kitchen countertop material.")

        result = service.create_structured_tasks(
            record=record,
            actions=[],
            decisions=[dec],
        )

        assert result.task_count == 0
        assert result.tasks == []

    def test_multiple_actions_create_distinct_tasks(self, service: TaskService) -> None:
        record = _make_record()
        a1 = _make_action("a-1", "Send structural drawing", "Architect will send drawing")
        a2 = _make_action("a-2", "Review drawing", "Britto Sir will review drawing")
        a3 = _make_action("a-3", "Confirm site visit", "Site supervisor to confirm visit")

        r1 = _make_responsibility("a-1", "Architect", "role")
        r2 = _make_responsibility("a-2", "Britto Sir", "person")
        # r3 missing

        d1 = _make_deadline("a-1", "Friday", "relative_day")
        # d2 missing
        d3 = _make_deadline("a-3", "tomorrow", "relative_day")

        result = service.create_structured_tasks(
            record=record,
            actions=[a1, a2, a3],
            responsibilities=[r1, r2],
            deadlines=[d1, d3],
        )

        assert result.task_count == 3
        tasks = result.tasks

        assert tasks[0].action_id == "a-1"
        assert tasks[0].responsible_party == "Architect"
        assert tasks[0].deadline == "Friday"

        assert tasks[1].action_id == "a-2"
        assert tasks[1].responsible_party == "Britto Sir"
        assert tasks[1].deadline is None
        assert tasks[1].deadline_type == "no_deadline"

        assert tasks[2].action_id == "a-3"
        assert tasks[2].responsible_party is None
        assert tasks[2].deadline == "tomorrow"

    def test_unknown_action_id_in_responsibility_raises_validation_error(self, service: TaskService) -> None:
        record = _make_record()
        action = _make_action("act-known", "Review design")
        bad_resp = _make_responsibility("act-UNKNOWN", "Architect")

        with pytest.raises(TaskValidationError, match="unknown action_id 'act-UNKNOWN'"):
            service.create_structured_tasks(
                record=record,
                actions=[action],
                responsibilities=[bad_resp],
            )

    def test_unknown_action_id_in_deadline_raises_validation_error(self, service: TaskService) -> None:
        record = _make_record()
        action = _make_action("act-known", "Review design")
        bad_dl = _make_deadline("act-UNKNOWN", "tomorrow")

        with pytest.raises(TaskValidationError, match="unknown action_id 'act-UNKNOWN'"):
            service.create_structured_tasks(
                record=record,
                actions=[action],
                deadlines=[bad_dl],
            )

    def test_server_side_created_at_is_utc_datetime(self, service: TaskService) -> None:
        record = _make_record()
        action = _make_action("act-001", "Action")

        result = service.create_structured_tasks(record=record, actions=[action])

        assert isinstance(result.created_at, datetime)
        assert result.created_at.tzinfo == timezone.utc
        assert isinstance(result.tasks[0].created_at, datetime)
        assert result.tasks[0].created_at.tzinfo == timezone.utc

    def test_explicit_status_detection_completed(self, service: TaskService) -> None:
        record = _make_record(raw_content="Foundation work is already completed yesterday.")
        action = _make_action("act-001", "Complete foundation work", "Foundation work is already completed")

        result = service.create_structured_tasks(record=record, actions=[action])
        assert result.tasks[0].status == "completed"

    def test_explicit_status_detection_blocked(self, service: TaskService) -> None:
        record = _make_record(raw_content="Electrical wiring is currently blocked due to water leakage.")
        action = _make_action("act-001", "Install electrical wiring", "Electrical wiring is currently blocked")

        result = service.create_structured_tasks(record=record, actions=[action])
        assert result.tasks[0].status == "blocked"

    def test_explicit_priority_detection_urgent(self, service: TaskService) -> None:
        record = _make_record(raw_content="This is an urgent task: please fix the slab crack immediately.")
        action = _make_action("act-001", "Fix slab crack", "urgent task: please fix the slab crack")

        result = service.create_structured_tasks(record=record, actions=[action])
        assert result.tasks[0].priority == "urgent"

    def test_explicit_priority_detection_high(self, service: TaskService) -> None:
        record = _make_record(raw_content="High priority: send revised estimates by today.")
        action = _make_action("act-001", "Send revised estimates", "High priority: send revised estimates")

        result = service.create_structured_tasks(record=record, actions=[action])
        assert result.tasks[0].priority == "high"

    def test_supports_extraction_result_containers(self, service: TaskService) -> None:
        record = _make_record()
        now = datetime.now(timezone.utc)
        action = _make_action("act-001", "Action 1")
        resp = _make_responsibility("act-001", "Architect")
        dl = _make_deadline("act-001", "Friday")
        dec = _make_decision()

        act_result = ActionExtractionResult(
            project_id=record.project_id,
            communication_id=record.communication_id,
            actions=[action],
            extracted_at=now,
            llm_model="fake-llm",
        )
        resp_result = ResponsibilityExtractionResult(
            project_id=record.project_id,
            communication_id=record.communication_id,
            assignments=[resp],
            extracted_at=now,
            llm_model="fake-llm",
        )
        dl_result = DeadlineExtractionResult(
            project_id=record.project_id,
            communication_id=record.communication_id,
            assignments=[dl],
            extracted_at=now,
            llm_model="fake-llm",
        )
        dec_result = DecisionExtractionResult(
            project_id=record.project_id,
            communication_id=record.communication_id,
            decisions=[dec],
            extracted_at=now,
            llm_model="fake-llm",
        )

        result = service.create_structured_tasks(
            record=record,
            actions=act_result,
            responsibilities=resp_result,
            deadlines=dl_result,
            decisions=dec_result,
        )

        assert result.task_count == 1
        assert result.tasks[0].responsible_party == "Architect"
        assert result.tasks[0].deadline == "Friday"
        assert len(result.tasks[0].decision_context) == 1
