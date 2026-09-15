"""
ArchScale — Module 2 Tests
Tests for the LLM provider abstraction layer.
"""

from __future__ import annotations

import json

import pytest

from app.llm.base import LLMMessage, LLMProviderError, LLMRequest
from app.llm.provider import FakeLLMProvider, create_provider, _default_fake_response


# ---------------------------------------------------------------------------
# FakeLLMProvider
# ---------------------------------------------------------------------------


class TestFakeLLMProvider:
    def test_returns_valid_json_response(self) -> None:
        provider = FakeLLMProvider()
        request = LLMRequest(messages=[LLMMessage(role="user", content="test")])
        response = provider.generate(request)

        assert response.text
        data = json.loads(response.text)
        assert "concise_summary" in data
        assert "topics" in data
        assert "stakeholders" in data
        assert "communication_type" in data
        assert "important_context" in data

    def test_provider_name_is_fake(self) -> None:
        provider = FakeLLMProvider()
        assert provider.provider_name == "fake"

    def test_custom_response(self) -> None:
        custom = {
            "concise_summary": "Custom summary.",
            "detailed_summary": "Custom detailed.",
            "topics": ["topic-A"],
            "stakeholders": ["Alice"],
            "communication_type": "update",
            "important_context": ["context-A"],
        }
        provider = FakeLLMProvider(fixed_response=custom)
        response = provider.generate(
            LLMRequest(messages=[LLMMessage(role="user", content="hi")])
        )
        data = json.loads(response.text)
        assert data["concise_summary"] == "Custom summary."
        assert data["stakeholders"] == ["Alice"]

    def test_should_fail_raises_provider_error(self) -> None:
        provider = FakeLLMProvider(should_fail=True)
        with pytest.raises(LLMProviderError, match="simulated provider failure"):
            provider.generate(
                LLMRequest(messages=[LLMMessage(role="user", content="hi")])
            )

    def test_bad_json_returns_invalid_text(self) -> None:
        provider = FakeLLMProvider(bad_json=True)
        response = provider.generate(
            LLMRequest(messages=[LLMMessage(role="user", content="hi")])
        )
        with pytest.raises(json.JSONDecodeError):
            json.loads(response.text)

    def test_usage_metadata_present(self) -> None:
        provider = FakeLLMProvider()
        response = provider.generate(
            LLMRequest(messages=[LLMMessage(role="user", content="hi")])
        )
        assert isinstance(response.usage, dict)
        assert "input" in response.usage
        assert "output" in response.usage


# ---------------------------------------------------------------------------
# create_provider factory
# ---------------------------------------------------------------------------


class TestCreateProviderFactory:
    def test_fake_provider_created(self) -> None:
        provider = create_provider("fake")
        assert provider.provider_name == "fake"

    def test_unsupported_provider_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Unsupported LLM provider"):
            create_provider("nonexistent_provider")

    def test_gemini_without_api_key_raises_provider_error(self) -> None:
        from app.llm.base import LLMProviderError

        with pytest.raises(LLMProviderError, match="LLM_API_KEY"):
            create_provider("gemini", api_key="")

    def test_fake_provider_kwargs_ignored(self) -> None:
        # Extra kwargs for fake provider should not raise
        provider = create_provider("fake", model="any-model", timeout=5)
        assert provider.provider_name == "fake"


# ---------------------------------------------------------------------------
# Default fake response schema
# ---------------------------------------------------------------------------


class TestDefaultFakeResponse:
    def test_contains_all_required_fields(self) -> None:
        resp = _default_fake_response()
        required = {
            "concise_summary",
            "detailed_summary",
            "topics",
            "stakeholders",
            "communication_type",
            "important_context",
        }
        assert required.issubset(resp.keys())

    def test_topics_and_stakeholders_are_lists(self) -> None:
        resp = _default_fake_response()
        assert isinstance(resp["topics"], list)
        assert isinstance(resp["stakeholders"], list)
        assert isinstance(resp["important_context"], list)

    def test_communication_type_is_valid(self) -> None:
        from app.models.understanding import VALID_COMMUNICATION_TYPES

        resp = _default_fake_response()
        assert resp["communication_type"] in VALID_COMMUNICATION_TYPES
