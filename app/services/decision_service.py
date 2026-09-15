"""
ArchScale — Module 6: Decision & Approval Extraction
Core service: orchestrates prompt construction, LLM call, schema boundary enforcement,
and server-side UUID generation for decision and approval extraction.
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
from app.models.communication import CommunicationRecord
from app.models.decision import (
    DecisionExtractionResult,
    ExtractedDecision,
    ExtractedDecisionPayload,
)
from app.models.understanding import UnderstandingResult
from app.prompts.decision import (
    DECISION_SYSTEM_PROMPT,
    build_decision_prompt,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class DecisionError(Exception):
    """Raised when decision extraction cannot be performed due to invalid input."""


class DecisionProviderError(Exception):
    """Raised when the LLM provider fails and cannot recover."""


class DecisionValidationError(Exception):
    """Raised when the LLM response fails validation or returns prohibited fields."""


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class DecisionService:
    """
    Stateless service that extracts confirmed decisions and approvals
    from a CommunicationRecord using an injected LLMProvider and contextual UnderstandingResult.
    Enforces strict schema boundaries (extra fields fail validation).
    """

    def __init__(self, llm_provider: LLMProvider) -> None:
        self._llm = llm_provider

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def extract_decisions(
        self,
        record: CommunicationRecord,
        understanding: UnderstandingResult | None = None,
    ) -> DecisionExtractionResult:
        """
        Extract confirmed decisions and approvals from a CommunicationRecord.

        Args:
            record: Fully ingested CommunicationRecord from Module 1.
            understanding: Optional Module 2 understanding result for context.

        Returns:
            DecisionExtractionResult with validated ExtractedDecision list.

        Raises:
            DecisionError:           Invalid / empty raw_content.
            DecisionProviderError:   LLM API failure.
            DecisionValidationError: Unparseable, extra fields, or invalid LLM response.
        """
        self._validate_record(record)

        request = self._build_request(record, understanding)
        raw_response = self._call_llm(request)
        result = self._parse_and_validate(raw_response, record)

        logger.info(
            "Extracted %d decisions/approvals from communication %s (project %s) via %s",
            len(result.decisions),
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
            raise DecisionError(
                "Cannot extract decisions from a communication with empty or whitespace-only content."
            )

    def _build_request(
        self,
        record: CommunicationRecord,
        understanding: UnderstandingResult | None,
    ) -> LLMRequest:
        """Construct the LLMRequest."""
        source_type = (
            record.source_type.value
            if hasattr(record.source_type, "value")
            else str(record.source_type)
        )
        user_prompt = build_decision_prompt(
            raw_content=record.raw_content,
            understanding=understanding,
            project_id=record.project_id,
            source_type=source_type,
        )
        return LLMRequest(
            messages=[
                LLMMessage(role="system", content=DECISION_SYSTEM_PROMPT),
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
                raise DecisionProviderError(
                    "LLM provider returned an empty response."
                )
            return response.text
        except LLMProviderError as exc:
            raise DecisionProviderError(
                f"LLM provider '{self._llm.provider_name}' failed: {exc}"
            ) from exc
        except LLMResponseError as exc:
            raise DecisionValidationError(
                f"LLM response error from '{self._llm.provider_name}': {exc}"
            ) from exc

    def _parse_and_validate(
        self,
        raw_text: str,
        record: CommunicationRecord,
    ) -> DecisionExtractionResult:
        """
        Parse LLM's JSON response, strictly validate against ExtractedDecisionPayload
        (failing if prohibited fields or decision_id are returned),
        and generate UUID4 decision IDs server-side.
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
            raise DecisionValidationError(
                f"LLM returned invalid JSON: {exc}. Raw response: {raw_text[:200]!r}"
            ) from exc

        if not isinstance(data, dict):
            raise DecisionValidationError(
                f"LLM response must be a JSON object, got {type(data).__name__}"
            )

        raw_decisions = data.get("decisions")
        if raw_decisions is None or not isinstance(raw_decisions, list):
            raise DecisionValidationError(
                "LLM response must contain a 'decisions' list."
            )

        # Step 3: validate each item with strict extra="forbid"
        decisions: list[ExtractedDecision] = []
        for idx, item in enumerate(raw_decisions):
            if not isinstance(item, dict):
                raise DecisionValidationError(
                    f"Decision item at index {idx} is not a valid JSON object."
                )

            # Strict Pydantic validation (extra="forbid"):
            # If the LLM returned extra keys (owner, responsible_party, deadline,
            # due_date, priority, task, decision_id, etc.), this will FAIL.
            try:
                payload = ExtractedDecisionPayload.model_validate(item)
            except ValidationError as exc:
                raise DecisionValidationError(
                    f"Decision at index {idx} failed schema boundary validation: {exc}"
                ) from exc

            # Generate server-side UUID4 decision_id
            decision = ExtractedDecision(
                decision_id=str(uuid4()),
                item_type=payload.item_type,
                description=payload.description,
                subject=payload.subject,
                status=payload.status,
                evidence=payload.evidence,
                confidence=payload.confidence,
            )
            decisions.append(decision)

        return DecisionExtractionResult(
            project_id=record.project_id,
            communication_id=record.communication_id,
            decisions=decisions,
            extracted_at=datetime.now(timezone.utc),
            llm_model=self._llm.provider_name,
        )
