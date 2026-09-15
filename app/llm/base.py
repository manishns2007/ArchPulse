"""
ArchScale — Module 2: Communication Understanding
LLM abstraction: base class and shared types.

All concrete providers must implement LLMProvider.
The understanding service depends ONLY on this interface.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Shared value objects
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LLMMessage:
    """A single message in a prompt conversation."""

    role: str  # "system" | "user" | "assistant"
    content: str


@dataclass
class LLMRequest:
    """
    Provider-independent request to generate structured output.

    Attributes:
        messages:       Ordered list of conversation messages.
        response_schema: Optional dict describing the JSON schema the LLM
                         should conform to (used by providers that support
                         structured/constrained output).
        temperature:    Sampling temperature (0.0 = deterministic).
        max_tokens:     Upper bound on response tokens.
    """

    messages: list[LLMMessage]
    response_schema: dict[str, Any] | None = None
    temperature: float = 0.1
    max_tokens: int = 2048


@dataclass
class LLMResponse:
    """
    Provider-independent response from the LLM.

    Attributes:
        text:       Raw text content returned by the provider.
        model:      The model name / version that produced the response.
        usage:      Token usage dict, e.g. {"input": 120, "output": 340}.
        raw:        The original provider response object, for debugging.
    """

    text: str
    model: str = ""
    usage: dict[str, int] = field(default_factory=dict)
    raw: Any = None


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class LLMProviderError(Exception):
    """Raised when the LLM provider returns an error or times out."""


class LLMResponseError(Exception):
    """Raised when the LLM response cannot be parsed or validated."""


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------


class LLMProvider(ABC):
    """
    Abstract base class for all LLM provider implementations.

    To add a new provider (e.g. OpenAI, Ollama, Anthropic), subclass this
    and implement `generate`.  The understanding service never imports a
    concrete provider directly — it receives one via dependency injection.
    """

    @abstractmethod
    def generate(self, request: LLMRequest) -> LLMResponse:
        """
        Send a generation request to the LLM and return a response.

        Args:
            request: Provider-independent generation request.

        Returns:
            LLMResponse with the raw text from the model.

        Raises:
            LLMProviderError: On API errors, timeouts, or rate-limits.
            LLMResponseError: On malformed/empty responses.
        """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Human-readable provider name (e.g. 'gemini', 'openai')."""
