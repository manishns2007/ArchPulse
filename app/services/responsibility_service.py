"""
ArchScale — Module 4: Responsibility Detection
Core service: orchestrates prompt construction, LLM call, schema boundary enforcement,
server-side UUID generation, and action ID validation.
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
from app.models.responsibility import (
    ResponsibilityAssignment,
    ResponsibilityAssignmentPayload,
    ResponsibilityExtractionResult,
)
from app.models.understanding import UnderstandingResult
from app.prompts.responsibility import (
    RESPONSIBILITY_SYSTEM_PROMPT,
    build_responsibility_prompt,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class ResponsibilityError(Exception):
    """Raised when responsibility detection cannot be performed due to invalid input."""


class ResponsibilityProviderError(Exception):
    """Raised when the LLM provider fails and cannot recover."""


class ResponsibilityValidationError(Exception):
    """Raised when the LLM response fails validation, returns prohibited fields, or unknown action_id."""


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class ResponsibilityService:
    """
    Stateless service that detects responsibility for extracted actions
    using an injected LLMProvider and contextual UnderstandingResult.
    Enforces strict schema boundaries (extra fields fail validation).
    """

    def __init__(self, llm_provider: LLMProvider) -> None:
        self._llm = llm_provider

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def detect_responsibilities(
        self,
        record: CommunicationRecord,
        actions: list[ExtractedAction] | ActionExtractionResult,
        understanding: UnderstandingResult | None = None,
    ) -> ResponsibilityExtractionResult:
        """
        Detect responsibility for a list of Module 3 actions.

        Args:
            record: Fully ingested CommunicationRecord from Module 1.
            actions: List of ExtractedAction (or ActionExtractionResult) from Module 3.
            understanding: Optional Module 2 understanding result for context.

        Returns:
            ResponsibilityExtractionResult with validated ResponsibilityAssignment list.

        Raises:
            ResponsibilityError:           Invalid / empty raw_content.
            ResponsibilityProviderError:   LLM API failure.
            ResponsibilityValidationError: Unparseable, extra fields, or unknown action_id.
        """
        self._validate_record(record)

        # Normalize actions input
        action_list: list[ExtractedAction] = (
            actions.actions if isinstance(actions, ActionExtractionResult) else actions
        )

        # If no actions to assign, return empty result immediately
        if not action_list:
            logger.info(
                "No actions provided for communication %s; returning empty responsibility result.",
                record.communication_id,
            )
            return ResponsibilityExtractionResult(
                project_id=record.project_id,
                communication_id=record.communication_id,
                assignments=[],
                extracted_at=datetime.now(timezone.utc),
                llm_model=self._llm.provider_name,
            )

        request = self._build_request(record, action_list, understanding)
        raw_response = self._call_llm(request)
        result = self._parse_and_validate(raw_response, record, action_list)

        logger.info(
            "Detected %d responsibility assignments for communication %s (project %s) via %s",
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
            raise ResponsibilityError(
                "Cannot detect responsibility from a communication with empty or whitespace-only content."
            )

    def _build_request(
        self,
        record: CommunicationRecord,
        actions: list[ExtractedAction],
        understanding: UnderstandingResult | None,
    ) -> LLMRequest:
        """Construct the LLMRequest."""
        source_type = (
            record.source_type.value
            if hasattr(record.source_type, "value")
            else str(record.source_type)
        )
        user_prompt = build_responsibility_prompt(
            raw_content=record.raw_content,
            actions=actions,
            understanding=understanding,
            project_id=record.project_id,
            source_type=source_type,
        )
        return LLMRequest(
            messages=[
                LLMMessage(role="system", content=RESPONSIBILITY_SYSTEM_PROMPT),
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
                raise ResponsibilityProviderError(
                    "LLM provider returned an empty response."
                )
            return response.text
        except LLMProviderError as exc:
            raise ResponsibilityProviderError(
                f"LLM provider '{self._llm.provider_name}' failed: {exc}"
            ) from exc
        except LLMResponseError as exc:
            raise ResponsibilityValidationError(
                f"LLM response error from '{self._llm.provider_name}': {exc}"
            ) from exc

    def _parse_and_validate(
        self,
        raw_text: str,
        record: CommunicationRecord,
        actions: list[ExtractedAction],
    ) -> ResponsibilityExtractionResult:
        """
        Parse the LLM's JSON response, strictly validate against ResponsibilityAssignmentPayload
        (failing if prohibited fields or responsibility_id are returned),
        generate UUID4 responsibility IDs server-side, and validate action IDs.
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
            raise ResponsibilityValidationError(
                f"LLM returned invalid JSON: {exc}. Raw response: {raw_text[:200]!r}"
            ) from exc

        if not isinstance(data, dict):
            raise ResponsibilityValidationError(
                f"LLM response must be a JSON object, got {type(data).__name__}"
            )

        raw_assignments = data.get("assignments")
        if raw_assignments is None or not isinstance(raw_assignments, list):
            raise ResponsibilityValidationError(
                "LLM response must contain an 'assignments' list."
            )

        valid_action_ids = {a.action_id for a in actions}

        # Step 3: validate each assignment item with strict extra="forbid"
        assignments: list[ResponsibilityAssignment] = []
        assigned_action_ids: set[str] = set()

        for idx, item in enumerate(raw_assignments):
            if not isinstance(item, dict):
                raise ResponsibilityValidationError(
                    f"Assignment at index {idx} is not a valid JSON object."
                )

            # Strict Pydantic validation (extra="forbid"):
            # If the LLM returned extra keys (owner, deadline, due_date, decision,
            # approval, priority, status, responsibility_id, etc.), this will FAIL.
            try:
                payload = ResponsibilityAssignmentPayload.model_validate(item)
            except ValidationError as exc:
                raise ResponsibilityValidationError(
                    f"Assignment at index {idx} failed schema boundary validation: {exc}"
                ) from exc

            # Validate that action_id exists in Module 3 actions
            if payload.action_id not in valid_action_ids:
                raise ResponsibilityValidationError(
                    f"Assignment at index {idx} references unknown action_id '{payload.action_id}'. "
                    f"Expected one of: {sorted(valid_action_ids)}"
                )

            # Generate server-side UUID4 responsibility_id
            assignment = ResponsibilityAssignment(
                responsibility_id=str(uuid4()),
                action_id=payload.action_id,
                responsible_party=payload.responsible_party,
                responsibility_type=payload.responsibility_type,
                evidence=payload.evidence,
                confidence=payload.confidence,
            )
            assignments.append(assignment)
            assigned_action_ids.add(payload.action_id)

        # Ensure all supplied Module 3 actions have an assignment;
        # if the LLM omitted any action, attach an unknown assignment as a safeguard.
        for action in actions:
            if action.action_id not in assigned_action_ids:
                assignments.append(
                    ResponsibilityAssignment(
                        responsibility_id=str(uuid4()),
                        action_id=action.action_id,
                        responsible_party=None,
                        responsibility_type="unknown",
                        evidence=None,
                        confidence=0.0,
                    )
                )

        return ResponsibilityExtractionResult(
            project_id=record.project_id,
            communication_id=record.communication_id,
            assignments=assignments,
            extracted_at=datetime.now(timezone.utc),
            llm_model=self._llm.provider_name,
        )
