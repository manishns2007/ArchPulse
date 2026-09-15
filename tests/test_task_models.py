"""
ArchScale — Module 7 Tests
Unit tests for Task Pydantic models (app/models/task.py).
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from app.models.task import (
    StructuredTask,
    StructuredTaskResult,
    TaskPriority,
    TaskStatus,
    VALID_TASK_PRIORITIES,
    VALID_TASK_STATUSES,
)


class TestTaskModels:
    def test_default_status_is_pending(self) -> None:
        task = StructuredTask(
            project_id="proj-villa",
            communication_id="test-comm-001",
            action_id="act-001",
            title="Send the structural drawing",
            description="Send the structural drawing by Friday.",
            evidence="Architect will send the structural drawing by Friday.",
        )
        assert task.status == "pending"

    def test_default_priority_is_unspecified(self) -> None:
        task = StructuredTask(
            project_id="proj-villa",
            communication_id="test-comm-001",
            action_id="act-001",
            title="Send the structural drawing",
            description="Send the structural drawing by Friday.",
            evidence="Architect will send the structural drawing by Friday.",
        )
        assert task.priority == "unspecified"

    def test_task_id_generated_as_uuid(self) -> None:
        task = StructuredTask(
            project_id="proj-villa",
            communication_id=uuid4(),
            action_id=uuid4(),
            title="Send the structural drawing",
            description="Send the structural drawing by Friday.",
            evidence="Architect will send the structural drawing by Friday.",
        )
        assert isinstance(task.task_id, UUID)
        assert task.task_id.version == 4

    def test_extra_fields_forbidden_on_structured_task(self) -> None:
        with pytest.raises(ValidationError):
            StructuredTask(
                project_id="proj-villa",
                communication_id="test-comm-001",
                action_id="act-001",
                title="Send the structural drawing",
                description="Send the structural drawing by Friday.",
                evidence="Architect will send the structural drawing by Friday.",
                unexpected_field="disallowed",  # type: ignore[call-arg]
            )

    def test_extra_fields_forbidden_on_task_result(self) -> None:
        with pytest.raises(ValidationError):
            StructuredTaskResult(
                project_id="proj-villa",
                communication_id="test-comm-001",
                tasks=[],
                task_count=0,
                forbidden_extra="disallowed",  # type: ignore[call-arg]
            )

    def test_all_valid_statuses_accepted(self) -> None:
        for s in VALID_TASK_STATUSES:
            task = StructuredTask(
                project_id="proj-villa",
                communication_id="test-comm-001",
                action_id="act-001",
                title="Task",
                description="Desc",
                status=s,  # type: ignore[arg-type]
                evidence="Evidence text",
            )
            assert task.status == s

    def test_invalid_status_normalizes_to_pending(self) -> None:
        task = StructuredTask(
            project_id="proj-villa",
            communication_id="test-comm-001",
            action_id="act-001",
            title="Task",
            description="Desc",
            status="not_a_status",  # type: ignore[arg-type]
            evidence="Evidence text",
        )
        assert task.status == "pending"

    def test_all_valid_priorities_accepted(self) -> None:
        for p in VALID_TASK_PRIORITIES:
            task = StructuredTask(
                project_id="proj-villa",
                communication_id="test-comm-001",
                action_id="act-001",
                title="Task",
                description="Desc",
                priority=p,  # type: ignore[arg-type]
                evidence="Evidence text",
            )
            assert task.priority == p

    def test_invalid_priority_normalizes_to_unspecified(self) -> None:
        task = StructuredTask(
            project_id="proj-villa",
            communication_id="test-comm-001",
            action_id="act-001",
            title="Task",
            description="Desc",
            priority="super_critical",  # type: ignore[arg-type]
            evidence="Evidence text",
        )
        assert task.priority == "unspecified"

    def test_empty_title_or_description_raises_validation_error(self) -> None:
        with pytest.raises(ValidationError):
            StructuredTask(
                project_id="proj-villa",
                communication_id="test-comm-001",
                action_id="act-001",
                title="   ",
                description="Desc",
                evidence="Evidence",
            )
        with pytest.raises(ValidationError):
            StructuredTask(
                project_id="proj-villa",
                communication_id="test-comm-001",
                action_id="act-001",
                title="Title",
                description="   ",
                evidence="Evidence",
            )
