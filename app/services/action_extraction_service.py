"""
ArchScale — Module 3: Action Extraction
Core service: orchestrates prompt construction, LLM call, UUID generation, and validation.
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
from app.models.understanding import UnderstandingResult
from app.prompts.action_extraction import (
    ACTION_EXTRACTION_SYSTEM_PROMPT,
    build_action_extraction_prompt,
)

logger = logging.getLogger(__name__)

# Keys strictly prohibited from Module 3 output
PROHIBITED_ACTION_KEYS = frozenset({
    "owner",
    "responsible_person",
    "responsible",
    "assignee",
    "deadline",
    "due_date",
    "date",
    "decision",
    "approval",
})


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class ActionExtractionError(Exception):
    """Raised when extraction cannot be performed due to invalid input."""


class ActionExtractionProviderError(Exception):
    """Raised when the LLM provider fails and cannot recover."""


class ActionExtractionValidationError(Exception):
    """Raised when the LLM response fails validation or JSON parsing."""


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class ActionExtractionService:
    """
    Stateless service that extracts actionable tasks from a CommunicationRecord
    using an injected LLMProvider and contextual UnderstandingResult.
    """

    def __init__(self, llm_provider: LLMProvider) -> None:
        self._llm = llm_provider
        self._cache: dict[str, ActionExtractionResult] = {}

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def clear_cache(self) -> None:
        """Clear cached action extraction results."""
        self._cache.clear()

    def extract_actions(
        self,
        record: CommunicationRecord,
        understanding: UnderstandingResult | None = None,
        use_cache: bool = True,
    ) -> ActionExtractionResult:
        """
        Extract actions from a CommunicationRecord.

        Args:
            record: A fully ingested CommunicationRecord from Module 1.
            understanding: Optional Module 2 understanding result for context.
            use_cache: If True, reuse previously extracted actions for this record.

        Returns:
            ActionExtractionResult with validated ExtractedAction list.

        Raises:
            ActionExtractionError:           Invalid / empty raw_content.
            ActionExtractionProviderError:   LLM API failure.
            ActionExtractionValidationError: Unparseable or invalid LLM response.
        """
        if use_cache and record.communication_id in self._cache:
            return self._cache[record.communication_id]

        self._validate_record(record)

        request = self._build_request(record, understanding)
        raw_response = self._call_llm(request)
        result = self._parse_and_validate(raw_response, record)

        logger.info(
            "Extracted %d actions from communication %s (project %s) via %s",
            len(result.actions),
            record.communication_id,
            record.project_id,
            self._llm.provider_name,
        )
        self._cache[record.communication_id] = result
        return result

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _validate_record(self, record: CommunicationRecord) -> None:
        """Guard against empty or invalid communication content."""
        if not record.raw_content or not record.raw_content.strip():
            raise ActionExtractionError(
                "Cannot extract actions from a communication with empty or whitespace-only content."
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
        user_prompt = build_action_extraction_prompt(
            raw_content=record.raw_content,
            understanding=understanding,
            project_id=record.project_id,
            source_type=source_type,
        )
        return LLMRequest(
            messages=[
                LLMMessage(role="system", content=ACTION_EXTRACTION_SYSTEM_PROMPT),
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
                raise ActionExtractionProviderError(
                    "LLM provider returned an empty response."
                )
            return response.text
        except LLMProviderError as exc:
            raise ActionExtractionProviderError(
                f"LLM provider '{self._llm.provider_name}' failed: {exc}"
            ) from exc
        except LLMResponseError as exc:
            raise ActionExtractionValidationError(
                f"LLM response error from '{self._llm.provider_name}': {exc}"
            ) from exc

    def _parse_and_validate(
        self,
        raw_text: str,
        record: CommunicationRecord,
    ) -> ActionExtractionResult:
        """
        Parse the LLM's JSON response, generate UUID4 action IDs server-side,
        strip any prohibited fields defensively, and validate ExtractedAction list.
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
            raise ActionExtractionValidationError(
                f"LLM returned invalid JSON: {exc}. Raw response: {raw_text[:200]!r}"
            ) from exc

        if not isinstance(data, dict):
            raise ActionExtractionValidationError(
                f"LLM response must be a JSON object, got {type(data).__name__}"
            )

        raw_actions = data.get("actions")
        if raw_actions is None or not isinstance(raw_actions, list):
            raise ActionExtractionValidationError(
                "LLM response must contain an 'actions' list."
            )

        # Step 3: validate and assign action_id server-side
        actions: list[ExtractedAction] = []
        for idx, item in enumerate(raw_actions):
            if not isinstance(item, dict):
                raise ActionExtractionValidationError(
                    f"Action at index {idx} is not a valid JSON object."
                )

            # Defensive cleanup: strip prohibited fields (Module 4+ responsibility)
            cleaned_item = {
                k: v for k, v in item.items()
                if k.lower() not in PROHIBITED_ACTION_KEYS
            }

            # Always generate UUID4 server-side
            cleaned_item["action_id"] = str(uuid4())

            try:
                action_obj = ExtractedAction.model_validate(cleaned_item)
                actions.append(action_obj)
            except ValidationError as exc:
                raise ActionExtractionValidationError(
                    f"Action at index {idx} failed schema validation: {exc}"
                ) from exc

        return ActionExtractionResult(
            project_id=record.project_id,
            communication_id=record.communication_id,
            actions=actions,
            extracted_at=datetime.now(timezone.utc),
            llm_model=self._llm.provider_name,
        )
