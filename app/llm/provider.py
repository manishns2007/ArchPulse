"""
ArchScale — Module 2: Communication Understanding
LLM provider implementations and factory.

Supported providers:
  - gemini  : Google Gemini via google-genai SDK
  - fake    : In-process stub for tests (no API calls)

To add a new provider, implement LLMProvider and register it in
`create_provider`.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.config import settings
from app.llm.base import (
    LLMMessage,
    LLMProvider,
    LLMProviderError,
    LLMRequest,
    LLMResponse,
    LLMResponseError,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Gemini provider
# ---------------------------------------------------------------------------


class GeminiProvider(LLMProvider):
    """
    Google Gemini provider via the `google-genai` SDK.

    Requires `LLM_API_KEY` to be set in the environment / .env file.
    Uses `gemini-2.0-flash` by default (configurable via `LLM_MODEL`).
    """

    def __init__(self, api_key: str, model: str, timeout: int, max_retries: int) -> None:
        self._api_key = api_key
        self._model = model
        self._timeout = timeout
        self._max_retries = max_retries
        self._client: Any = None  # lazy-initialised on first call

    def _get_client(self) -> Any:
        if self._client is None:
            try:
                import google.generativeai as genai  # type: ignore[import]
                genai.configure(api_key=self._api_key)
                self._client = genai.GenerativeModel(self._model)
            except ImportError as exc:
                raise LLMProviderError(
                    "google-generativeai is not installed. "
                    "Run: pip install google-generativeai"
                ) from exc
        return self._client

    @property
    def provider_name(self) -> str:
        return "gemini"

    def generate(self, request: LLMRequest) -> LLMResponse:
        """Send the prompt to Gemini and return the response text."""
        client = self._get_client()

        # Build the prompt — Gemini's SDK takes a single string or parts.
        # We flatten system + user messages into a structured prompt string.
        prompt_parts: list[str] = []
        for msg in request.messages:
            if msg.role == "system":
                prompt_parts.append(f"[SYSTEM]\n{msg.content}")
            elif msg.role == "user":
                prompt_parts.append(f"[USER]\n{msg.content}")
            else:
                prompt_parts.append(msg.content)

        full_prompt = "\n\n".join(prompt_parts)

        attempt = 0
        last_exc: Exception | None = None

        while attempt <= self._max_retries:
            try:
                response = client.generate_content(
                    full_prompt,
                    generation_config={
                        "temperature": request.temperature,
                        "max_output_tokens": request.max_tokens,
                        "response_mime_type": "application/json",
                    },
                )
                text = response.text
                if not text or not text.strip():
                    raise LLMResponseError("Gemini returned an empty response.")
                return LLMResponse(
                    text=text.strip(),
                    model=self._model,
                    raw=response,
                )
            except LLMResponseError:
                raise
            except Exception as exc:
                last_exc = exc
                attempt += 1
                logger.warning(
                    "Gemini request failed (attempt %d/%d): %s",
                    attempt,
                    self._max_retries + 1,
                    exc,
                )

        raise LLMProviderError(
            f"Gemini provider failed after {self._max_retries + 1} attempts: {last_exc}"
        ) from last_exc


# ---------------------------------------------------------------------------
# FakeProvider — deterministic stub for tests
# ---------------------------------------------------------------------------


class FakeLLMProvider(LLMProvider):
    """
    Deterministic in-process LLM stub for testing.

    Returns a pre-configured `fixed_response` JSON string.
    If `should_fail` is True, raises LLMProviderError on every call.
    If `bad_json` is True, returns syntactically invalid JSON.
    """

    def __init__(
        self,
        fixed_response: dict[str, Any] | None = None,
        should_fail: bool = False,
        bad_json: bool = False,
    ) -> None:
        self._fixed_response = fixed_response
        self._should_fail = should_fail
        self._bad_json = bad_json

    @property
    def provider_name(self) -> str:
        return "fake"

    def generate(self, request: LLMRequest) -> LLMResponse:
        if self._should_fail:
            raise LLMProviderError("FakeLLMProvider: simulated provider failure.")
        if self._bad_json:
            return LLMResponse(text="this is not valid json {{{{", model="fake")

        if self._fixed_response is not None:
            data = self._fixed_response
        else:
            full_prompt = " ".join(m.content for m in request.messages)
            if (
                "responsibility types" in full_prompt.lower()
                or "actions to assign responsibility for" in full_prompt.lower()
            ):
                data = _default_fake_responsibility_response(full_prompt)
            elif "actions" in full_prompt.lower() or "actionable" in full_prompt.lower():
                data = _default_fake_actions_response()
            else:
                data = _default_fake_response()

        return LLMResponse(
            text=json.dumps(data),
            model="fake-model-v1",
            usage={"input": 10, "output": 20},
        )


def _default_fake_responsibility_response(prompt: str = "") -> dict[str, Any]:
    """The default structured responsibility response returned by FakeLLMProvider."""
    import re

    if "=== ACTIONS TO ASSIGN RESPONSIBILITY FOR" in prompt:
        actions_section = prompt.split("=== ACTIONS TO ASSIGN RESPONSIBILITY FOR", 1)[1]
        action_ids = re.findall(r'"action_id":\s*"([^"]+)"', actions_section)
    else:
        action_ids = [
            aid for aid in re.findall(r'"action_id":\s*"([^"]+)"', prompt)
            if not aid.startswith("<")
        ]
    if action_ids:
        assignments = []
        for idx, aid in enumerate(action_ids):
            if idx == 0:
                assignments.append({
                    "action_id": aid,
                    "responsible_party": "Architect",
                    "responsibility_type": "role",
                    "evidence": "Architect will send the structural drawing by Friday.",
                    "confidence": 0.95,
                })
            elif idx == 1:
                assignments.append({
                    "action_id": aid,
                    "responsible_party": "Contractor",
                    "responsibility_type": "role",
                    "evidence": "Contractor should verify the cabinet dimensions.",
                    "confidence": 0.90,
                })
            else:
                assignments.append({
                    "action_id": aid,
                    "responsible_party": None,
                    "responsibility_type": "unknown",
                    "evidence": None,
                    "confidence": 0.5,
                })
        return {"assignments": assignments}

    return {
        "assignments": [
            {
                "action_id": "default-act-1",
                "responsible_party": "Architect",
                "responsibility_type": "role",
                "evidence": "Architect will send the structural drawing by Friday.",
                "confidence": 0.95,
            }
        ]
    }


def _default_fake_actions_response() -> dict[str, Any]:
    """The default structured action extraction response returned by FakeLLMProvider."""
    return {
        "actions": [
            {
                "action": "Send the structural drawing",
                "evidence": "Architect will send the structural drawing by Friday.",
                "confidence": 0.95,
                "action_type": "deliverable",
            },
            {
                "action": "Verify the cabinet dimensions",
                "evidence": "Contractor should verify the cabinet dimensions.",
                "confidence": 0.88,
                "action_type": "task",
            },
        ]
    }


def _default_fake_response() -> dict[str, Any]:
    """The default structured response returned by FakeLLMProvider."""
    return {
        "concise_summary": "Discussion about the revised kitchen layout and upcoming structural drawing.",
        "detailed_summary": (
            "The client has approved the revised kitchen layout. "
            "The architect indicated that the structural drawing needs updating before the next site review. "
            "The contractor raised concerns about the revised cabinet dimensions."
        ),
        "topics": ["kitchen layout", "structural drawing", "site review", "cabinet dimensions"],
        "stakeholders": ["client", "architect", "contractor"],
        "communication_type": "mixed",
        "important_context": [
            "The revised kitchen layout has been approved by the client.",
            "A structural drawing update is referenced as a prerequisite.",
            "A site review is mentioned as a future milestone.",
            "Cabinet dimension concerns have been raised.",
        ],
    }


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def create_provider(
    provider_name: str | None = None,
    *,
    api_key: str | None = None,
    model: str | None = None,
    timeout: int | None = None,
    max_retries: int | None = None,
) -> LLMProvider:
    """
    Factory that returns the appropriate LLMProvider based on configuration.

    Falls back to settings if keyword arguments are not supplied.

    Supported `provider_name` values:
      - "gemini"  — Google Gemini
      - "fake"    — In-process test stub (no API calls)

    Raises:
        ValueError: If an unsupported provider name is given.
        LLMProviderError: If required configuration (e.g. API key) is missing.
    """
    name = (provider_name or settings.llm_provider).lower().strip()
    resolved_api_key = api_key if api_key is not None else settings.llm_api_key
    resolved_model = model if model is not None else settings.llm_model
    resolved_timeout = timeout if timeout is not None else settings.llm_timeout_seconds
    resolved_retries = max_retries if max_retries is not None else settings.llm_max_retries

    if name == "gemini":
        if not resolved_api_key:
            raise LLMProviderError(
                "LLM_API_KEY is required for the Gemini provider. "
                "Set it in your .env file or LLM_API_KEY environment variable."
            )
        return GeminiProvider(
            api_key=resolved_api_key,
            model=resolved_model,
            timeout=resolved_timeout,
            max_retries=resolved_retries,
        )

    if name == "fake":
        return FakeLLMProvider()

    raise ValueError(
        f"Unsupported LLM provider: '{name}'. "
        "Supported values: 'gemini', 'fake'."
    )
