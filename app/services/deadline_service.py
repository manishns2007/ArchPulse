"""
ArchScale — Module 5: Deadline Detection
Core service: orchestrates prompt construction, LLM call, schema boundary enforcement,
server-side UUID generation, and action ID validation for deadline detection.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from uuid import uuid4

from pydantic import ValidationError

from app.llm.base import (
    LLMMessage,
    LLMProvider,
    LLMProviderError,
    LLMRequest,
    LLMResponseError,
)
from app.models.action_extraction import (
    ActionExtractionResult,
    ExtractedAction,
)
from app.models.communication import CommunicationRecord
from app.models.deadline import (
    DeadlineAssignment,
    DeadlineAssignmentPayload,
    DeadlineExtractionResult,
)
from app.models.responsibility import (
    ResponsibilityAssignment,
    ResponsibilityExtractionResult,
)
from app.models.understanding import UnderstandingResult
from app.prompts.deadline import (
    DEADLINE_SYSTEM_PROMPT,
    build_deadline_prompt,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class DeadlineError(Exception):
    """Raised when deadline detection cannot be performed due to invalid input."""


class DeadlineProviderError(Exception):
    """Raised when the LLM provider fails and cannot recover."""


class DeadlineValidationError(Exception):
    """Raised when the LLM response fails validation, returns prohibited fields, or unknown action_id."""


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class DeadlineService:
    """
    Stateless service that detects deadlines for extracted actions
    using an injected LLMProvider, contextual UnderstandingResult, and Responsibility assignments.
    Enforces strict schema boundaries (extra fields fail validation).
    """

    def __init__(self, llm_provider: LLMProvider) -> None:
        self._llm = llm_provider

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def detect_deadlines(
        self,
        record: CommunicationRecord,
        actions: list[ExtractedAction] | ActionExtractionResult,
        understanding: UnderstandingResult | None = None,
        responsibilities: list[ResponsibilityAssignment] | ResponsibilityExtractionResult | None = None,
    ) -> DeadlineExtractionResult:
        """
        Detect deadlines for a list of Module 3 actions.

        Args:
            record: Fully ingested CommunicationRecord from Module 1.
            actions: List of ExtractedAction (or ActionExtractionResult) from Module 3.
            understanding: Optional Module 2 understanding result for context.
            responsibilities: Optional Module 4 responsibility result for context.

        Returns:
            DeadlineExtractionResult with 1-to-1 validated DeadlineAssignment list.

        Raises:
            DeadlineError:           Invalid / empty raw_content.
            DeadlineProviderError:   LLM API failure.
            DeadlineValidationError: Unparseable, extra fields, or unknown action_id.
        """
        self._validate_record(record)

        # Normalize actions input
        action_list: list[ExtractedAction] = (
            actions.actions if isinstance(actions, ActionExtractionResult) else actions
        )

        # If no actions to assign, return empty result immediately
        if not action_list:
            logger.info(
                "No actions provided for communication %s; returning empty deadline result.",
                record.communication_id,
            )
            return DeadlineExtractionResult(
                project_id=record.project_id,
                communication_id=record.communication_id,
                assignments=[],
                extracted_at=datetime.now(timezone.utc),
                llm_model=self._llm.provider_name,
            )

        # Normalize responsibilities input
        resp_list: list[ResponsibilityAssignment] | None = None
        if responsibilities is not None:
            resp_list = (
                responsibilities.assignments
                if isinstance(responsibilities, ResponsibilityExtractionResult)
                else responsibilities
            )

        request = self._build_request(record, action_list, understanding, resp_list)
        raw_response = self._call_llm(request)
        result = self._parse_and_validate(raw_response, record, action_list)

        logger.info(
            "Detected %d deadline assignments for communication %s (project %s) via %s",
            len(result.assignments),
            record.communication_id,
            record.project_id,
            self._llm.provider_name,
        )
        return result

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _validate_record(self, record: CommunicationRecord) -> None:
        """Guard against empty or whitespace-only communication content."""
        if not record.raw_content or not record.raw_content.strip():
            raise DeadlineError(
                "Cannot detect deadlines from a communication with empty or whitespace-only content."
            )

    def _build_request(
        self,
        record: CommunicationRecord,
        actions: list[ExtractedAction],
        understanding: UnderstandingResult | None,
        responsibilities: list[ResponsibilityAssignment] | None,
    ) -> LLMRequest:
        """Construct the LLMRequest."""
        source_type = (
            record.source_type.value
            if hasattr(record.source_type, "value")
            else str(record.source_type)
        )
        comm_ts = (
            record.timestamp.isoformat()
            if isinstance(record.timestamp, datetime)
            else str(record.timestamp)
        )
        user_prompt = build_deadline_prompt(
            raw_content=record.raw_content,
            actions=actions,
            communication_timestamp=comm_ts,
            understanding=understanding,
            responsibilities=responsibilities,
            project_id=record.project_id,
            source_type=source_type,
        )
        return LLMRequest(
            messages=[
                LLMMessage(role="system", content=DEADLINE_SYSTEM_PROMPT),
                LLMMessage(role="user", content=user_prompt),
            ],
            temperature=0.1,
            max_tokens=2048,
        )

    def _call_llm(self, request: LLMRequest) -> str:
        """Call LLM and return raw text."""
        try:
            response = self._llm.generate(request)
            if not response.text or not response.text.strip():
                raise DeadlineProviderError(
                    "LLM provider returned an empty response."
                )
            return response.text
        except LLMProviderError as exc:
            raise DeadlineProviderError(
                f"LLM provider '{self._llm.provider_name}' failed: {exc}"
            ) from exc
        except LLMResponseError as exc:
            raise DeadlineValidationError(
                f"LLM response error from '{self._llm.provider_name}': {exc}"
            ) from exc

    def _parse_and_validate(
        self,
        raw_text: str,
        record: CommunicationRecord,
        actions: list[ExtractedAction],
    ) -> DeadlineExtractionResult:
        """
        Parse LLM's JSON response, strictly validate against DeadlineAssignmentPayload
        (failing if prohibited fields or deadline_id are returned),
        generate UUID4 deadline IDs server-side, validate action IDs, and guarantee
        1-to-1 action-to-assignment coverage.
        """
        # Step 1: strip markdown code fences if present
        text = raw_text.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            inner = [
                ln for ln in lines[1:]
                if not ln.strip().startswith("```")
            ]
            text = "\n".join(inner).strip()

        # Step 2: parse JSON
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise DeadlineValidationError(
                f"LLM returned invalid JSON: {exc}. Raw response: {raw_text[:200]!r}"
            ) from exc

        if not isinstance(data, dict):
            raise DeadlineValidationError(
                f"LLM response must be a JSON object, got {type(data).__name__}"
            )

        raw_assignments = data.get("assignments")
        if raw_assignments is None or not isinstance(raw_assignments, list):
            raise DeadlineValidationError(
                "LLM response must contain an 'assignments' list."
            )

        valid_action_ids = {a.action_id for a in actions}

        # Step 3: validate each assignment item with strict extra="forbid"
        assignments: list[DeadlineAssignment] = []
        assigned_action_ids: set[str] = set()

        for idx, item in enumerate(raw_assignments):
            if not isinstance(item, dict):
                raise DeadlineValidationError(
                    f"Assignment at index {idx} is not a valid JSON object."
                )

            # Strict Pydantic validation (extra="forbid"):
            # If the LLM returned extra keys (owner, responsible_party, decision,
            # approval, priority, status, deadline_id, etc.), this will FAIL.
            try:
                payload = DeadlineAssignmentPayload.model_validate(item)
            except ValidationError as exc:
                raise DeadlineValidationError(
                    f"Assignment at index {idx} failed schema boundary validation: {exc}"
                ) from exc

            # Validate that action_id exists in Module 3 actions
            if payload.action_id not in valid_action_ids:
                raise DeadlineValidationError(
                    f"Assignment at index {idx} references unknown action_id '{payload.action_id}'. "
                    f"Expected one of: {sorted(valid_action_ids)}"
                )

            # Generate server-side UUID4 deadline_id
            assignment = DeadlineAssignment(
                deadline_id=str(uuid4()),
                action_id=payload.action_id,
                deadline=payload.deadline,
                deadline_type=payload.deadline_type,
                normalized_deadline=payload.normalized_deadline,
                evidence=payload.evidence,
                confidence=payload.confidence,
            )
            assignments.append(assignment)
            assigned_action_ids.add(payload.action_id)

        # Guarantee deterministic 1-to-1 mapping for every Module 3 action:
        # If the LLM omitted any action, attach the deterministic no_deadline assignment.
        for action in actions:
            if action.action_id not in assigned_action_ids:
                assignments.append(
                    DeadlineAssignment(
                        deadline_id=str(uuid4()),
                        action_id=action.action_id,
                        deadline=None,
                        deadline_type="no_deadline",
                        normalized_deadline=None,
                        evidence=None,
                        confidence=1.0,
                    )
                )

        return DeadlineExtractionResult(
            project_id=record.project_id,
            communication_id=record.communication_id,
            assignments=assignments,
            extracted_at=datetime.now(timezone.utc),
            llm_model=self._llm.provider_name,
        )
