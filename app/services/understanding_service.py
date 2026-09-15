"""
ArchScale — Module 2: Communication Understanding
Core service: orchestrates prompt construction, LLM call, and result validation.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from pydantic import ValidationError

from app.llm.base import (
    LLMMessage,
    LLMProvider,
    LLMProviderError,
    LLMRequest,
    LLMResponseError,
)
from app.models.communication import CommunicationRecord
from app.models.understanding import UnderstandingResult
from app.prompts.understanding import UNDERSTANDING_SYSTEM_PROMPT, build_user_prompt

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class UnderstandingError(Exception):
    """Raised when understanding cannot be generated due to invalid input."""


class UnderstandingProviderError(Exception):
    """Raised when the LLM provider fails and cannot recover."""


class UnderstandingValidationError(Exception):
    """Raised when the LLM response fails Pydantic validation."""


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class CommunicationUnderstandingService:
    """
    Stateless service that transforms a CommunicationRecord into an
    UnderstandingResult by calling the LLM provider.

    The provider is injected — the service has no direct dependency on any
    specific LLM SDK, making it trivially testable with a FakeLLMProvider.
    """

    def __init__(self, llm_provider: LLMProvider) -> None:
        self._llm = llm_provider

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def analyze(self, record: CommunicationRecord) -> UnderstandingResult:
        """
        Analyze a CommunicationRecord and return a structured UnderstandingResult.

        Args:
            record: A fully ingested CommunicationRecord from Module 1.

        Returns:
            UnderstandingResult with summary, topics, stakeholders, etc.

        Raises:
            UnderstandingError:           Invalid / empty raw_content.
            UnderstandingProviderError:   LLM API failure (unrecoverable).
            UnderstandingValidationError: LLM returned unparse-able JSON.
        """
        self._validate_record(record)

        request = self._build_request(record)
        raw_response = self._call_llm(request)
        result = self._parse_and_validate(raw_response, record)

        logger.info(
            "Understanding generated for communication %s (project %s) via %s",
            record.communication_id,
            record.project_id,
            self._llm.provider_name,
        )
        return result

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _validate_record(self, record: CommunicationRecord) -> None:
        """Guard against degenerate input before touching the LLM."""
        if not record.raw_content or not record.raw_content.strip():
            raise UnderstandingError(
                "Cannot analyze a communication with empty or whitespace-only content."
            )

    def _build_request(self, record: CommunicationRecord) -> LLMRequest:
        """Construct the provider-agnostic LLMRequest from a CommunicationRecord."""
        source_type = (
            record.source_type.value
            if hasattr(record.source_type, "value")
            else str(record.source_type)
        )
        user_prompt = build_user_prompt(
            raw_content=record.raw_content,
            source_type=source_type,
            project_id=record.project_id,
        )
        return LLMRequest(
            messages=[
                LLMMessage(role="system", content=UNDERSTANDING_SYSTEM_PROMPT),
                LLMMessage(role="user", content=user_prompt),
            ],
            temperature=0.1,
            max_tokens=2048,
        )

    def _call_llm(self, request: LLMRequest) -> str:
        """Call the LLM and return the raw text response."""
        try:
            response = self._llm.generate(request)
            if not response.text or not response.text.strip():
                raise UnderstandingProviderError(
                    "LLM provider returned an empty response."
                )
            return response.text
        except LLMProviderError as exc:
            raise UnderstandingProviderError(
                f"LLM provider '{self._llm.provider_name}' failed: {exc}"
            ) from exc
        except LLMResponseError as exc:
            raise UnderstandingValidationError(
                f"LLM response error from '{self._llm.provider_name}': {exc}"
            ) from exc

    def _parse_and_validate(
        self,
        raw_text: str,
        record: CommunicationRecord,
    ) -> UnderstandingResult:
        """
        Parse the LLM's JSON response and validate it against UnderstandingResult.

        Raises:
            UnderstandingValidationError: If JSON parsing or Pydantic validation fails.
        """
        # Step 1: clean up potential markdown code fences
        text = raw_text.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            # strip opening ``` line and closing ``` line
            inner = [
                ln for ln in lines[1:]
                if not ln.strip().startswith("```")
            ]
            text = "\n".join(inner).strip()

        # Step 2: parse JSON
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise UnderstandingValidationError(
                f"LLM returned invalid JSON: {exc}. Raw response: {raw_text[:200]!r}"
            ) from exc

        # Step 3: inject traceability fields from the source record
        data["project_id"] = record.project_id
        data["communication_id"] = record.communication_id
        data["analyzed_at"] = datetime.now(timezone.utc).isoformat()
        data["llm_model"] = self._llm.provider_name

        # Step 4: Pydantic validation
        try:
            return UnderstandingResult.model_validate(data)
        except ValidationError as exc:
            raise UnderstandingValidationError(
                f"LLM response failed schema validation: {exc}"
            ) from exc
