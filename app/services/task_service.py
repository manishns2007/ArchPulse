"""
ArchScale — Module 7: Conversation -> Structured Task
Core service: orchestrates composition, normalization, and traceability of structured tasks
from Modules 3-6 without rediscovering or duplicating extractions.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from uuid import uuid4

from app.models.action_extraction import (
    ActionExtractionResult,
    ExtractedAction,
)
from app.models.communication import CommunicationRecord
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
    TaskPriority,
    TaskStatus,
)
from app.models.understanding import UnderstandingResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class TaskError(Exception):
    """Raised when task structuring cannot be performed due to invalid input."""


class TaskValidationError(Exception):
    """Raised when upstream mappings reference unknown action IDs or fail validation."""


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class TaskService:
    """
    Stateless composition service that synthesizes already-extracted communication
    intelligence from Modules 3-6 into canonical StructuredTask items.
    """

    def create_structured_tasks(
        self,
        record: CommunicationRecord,
        actions: list[ExtractedAction] | ActionExtractionResult,
        responsibilities: list[ResponsibilityAssignment] | ResponsibilityExtractionResult | None = None,
        deadlines: list[DeadlineAssignment] | DeadlineExtractionResult | None = None,
        decisions: list[ExtractedDecision] | DecisionExtractionResult | None = None,
        understanding: UnderstandingResult | None = None,
    ) -> StructuredTaskResult:
        """
        Compose structured tasks from upstream module results.

        Args:
            record: Fully ingested CommunicationRecord from Module 1.
            actions: List of ExtractedAction (or ActionExtractionResult) from Module 3.
            responsibilities: Optional Module 4 responsibility assignments.
            deadlines: Optional Module 5 deadline assignments.
            decisions: Optional Module 6 decisions/approvals.
            understanding: Optional Module 2 understanding result.

        Returns:
            StructuredTaskResult with 1-to-1 composed StructuredTask list.

        Raises:
            TaskError: Invalid / empty raw_content.
            TaskValidationError: If upstream responsibility/deadline references unknown action_id.
        """
        self._validate_record(record)

        # Normalize input action list
        action_list: list[ExtractedAction] = (
            actions.actions if isinstance(actions, ActionExtractionResult) else actions
        )

        # Normalize input responsibilities
        resp_list: list[ResponsibilityAssignment] = []
        if responsibilities is not None:
            resp_list = (
                responsibilities.assignments
                if isinstance(responsibilities, ResponsibilityExtractionResult)
                else responsibilities
            )

        # Normalize input deadlines
        dl_list: list[DeadlineAssignment] = []
        if deadlines is not None:
            dl_list = (
                deadlines.assignments
                if isinstance(deadlines, DeadlineExtractionResult)
                else deadlines
            )

        # Normalize input decisions
        dec_list: list[ExtractedDecision] = []
        if decisions is not None:
            dec_list = (
                decisions.decisions
                if isinstance(decisions, DecisionExtractionResult)
                else decisions
            )

        # If no actions from Module 3, return empty task result immediately
        if not action_list:
            logger.info(
                "No actions provided for communication %s; returning empty structured task result.",
                record.communication_id,
            )
            return StructuredTaskResult(
                project_id=record.project_id,
                communication_id=record.communication_id,
                tasks=[],
                created_at=datetime.now(timezone.utc),
                task_count=0,
            )

        # Validate action ID integrity: all M4 and M5 assignments must link to known M3 actions
        known_action_ids = {str(a.action_id) for a in action_list}

        for r in resp_list:
            if str(r.action_id) not in known_action_ids:
                raise TaskValidationError(
                    f"Responsibility assignment references unknown action_id '{r.action_id}'. "
                    f"Expected one of: {sorted(known_action_ids)}"
                )

        for d in dl_list:
            if str(d.action_id) not in known_action_ids:
                raise TaskValidationError(
                    f"Deadline assignment references unknown action_id '{d.action_id}'. "
                    f"Expected one of: {sorted(known_action_ids)}"
                )

        # Build lookup maps for M4 and M5 by action_id
        resp_map = {str(r.action_id): r for r in resp_list}
        dl_map = {str(d.action_id): d for d in dl_list}

        # Build decision context strings from M6
        decision_context: list[str] = []
        for dec in dec_list:
            ctx_str = dec.evidence.strip() if dec.evidence else dec.description.strip()
            if ctx_str and ctx_str not in decision_context:
                decision_context.append(ctx_str)

        # Compose exactly one StructuredTask per M3 action
        tasks: list[StructuredTask] = []
        for action in action_list:
            aid_str = str(action.action_id)
            resp_item = resp_map.get(aid_str)
            dl_item = dl_map.get(aid_str)

            # Responsibility mapping
            responsible_party = resp_item.responsible_party if resp_item else None
            responsibility_type = resp_item.responsibility_type if resp_item else None

            # Deadline mapping
            deadline = dl_item.deadline if dl_item else None
            deadline_type = dl_item.deadline_type if dl_item else "no_deadline"
            normalized_deadline = dl_item.normalized_deadline if dl_item else None

            # Title and Description
            title = action.action.strip()
            description = self._compose_description(
                action=action,
                raw_content=record.raw_content,
                understanding=understanding,
                decisions=dec_list,
            )

            # Status and Priority
            status = self._detect_status(record.raw_content, action.evidence)
            priority = self._detect_priority(record.raw_content, action.evidence)

            task = StructuredTask(
                task_id=uuid4(),
                project_id=record.project_id,
                communication_id=record.communication_id,
                action_id=action.action_id,
                title=title,
                description=description,
                responsible_party=responsible_party,
                responsibility_type=responsibility_type,
                deadline=deadline,
                deadline_type=deadline_type,
                normalized_deadline=normalized_deadline,
                status=status,
                priority=priority,
                evidence=action.evidence.strip(),
                decision_context=decision_context,
                created_at=datetime.now(timezone.utc),
            )
            tasks.append(task)

        logger.info(
            "Structured %d tasks from communication %s (project %s)",
            len(tasks),
            record.communication_id,
            record.project_id,
        )

        return StructuredTaskResult(
            project_id=record.project_id,
            communication_id=record.communication_id,
            tasks=tasks,
            created_at=datetime.now(timezone.utc),
            task_count=len(tasks),
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _validate_record(self, record: CommunicationRecord) -> None:
        """Guard against empty or whitespace-only communication content."""
        if not record.raw_content or not record.raw_content.strip():
            raise TaskError(
                "Cannot structure tasks from a communication with empty or whitespace-only content."
            )

    def _compose_description(
        self,
        action: ExtractedAction,
        raw_content: str,
        understanding: UnderstandingResult | None,
        decisions: list[ExtractedDecision],
    ) -> str:
        """
        Synthesize a grounded task description from the M3 action, raw communication,
        and contextual M2/M6 information without hallucinating new facts.
        """
        base = action.action.strip()

        # If relevant M6 decision/approval context is available, mention it
        for dec in decisions:
            if dec.subject and dec.subject.lower() in raw_content.lower():
                # e.g., "Send the structural drawing for the revised kitchen layout."
                if dec.subject.lower() not in base.lower():
                    return f"{base} for the {dec.subject}."

        # If M2 concise summary provides clear context:
        if understanding and understanding.concise_summary:
            summary = understanding.concise_summary.strip().rstrip(".")
            if summary.lower() not in base.lower():
                return f"{base}. Context: {summary}."

        # Default clean description
        if not base.endswith("."):
            return f"{base}."
        return base

    def _detect_status(self, raw_content: str, evidence: str) -> TaskStatus:
        """
        Determine task status from explicit statements in the communication or evidence.
        Defaults to 'pending'.
        """
        text = f"{raw_content} {evidence}".lower()

        # Completed markers
        if any(p in text for p in [
            "is now complete",
            "is complete",
            "has been completed",
            "already completed",
            "is finished",
            "already done",
            "task completed",
        ]):
            return "completed"

        # Blocked markers
        if any(p in text for p in [
            "is blocked",
            "currently blocked",
            "blocked because",
            "on hold",
            "work is halted",
        ]):
            return "blocked"

        # In progress markers
        if any(p in text for p in [
            "in progress",
            "currently working on",
            "work is underway",
            "is underway",
        ]):
            return "in_progress"

        # Cancelled markers
        if any(p in text for p in [
            "is cancelled",
            "is canceled",
            "has been cancelled",
            "has been canceled",
            "task scrapped",
        ]):
            return "cancelled"

        return "pending"

    def _detect_priority(self, raw_content: str, evidence: str) -> TaskPriority:
        """
        Determine task priority from explicit statements in the communication or evidence.
        Defaults to 'unspecified'. Never infers priority from deadlines or importance.
        """
        text = f"{raw_content} {evidence}".lower()

        # Urgent markers
        if re.search(r"\b(urgent|urgently|asap|emergency|critical priority)\b", text):
            return "urgent"

        # High priority markers
        if re.search(r"\b(high priority|top priority|treat as high priority|priority:\s*high)\b", text):
            return "high"

        # Medium priority markers
        if re.search(r"\b(medium priority|normal priority|priority:\s*medium)\b", text):
            return "medium"

        # Low priority markers
        if re.search(r"\b(low priority|minor priority|priority:\s*low)\b", text):
            return "low"

        return "unspecified"
