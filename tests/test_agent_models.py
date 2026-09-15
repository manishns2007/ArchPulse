"""
ArchScale — Module 9: Agentic Project Query & User Interaction
Tests for Agent Pydantic v2 data models.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.models.agent import (
    AgentQueryRequest,
    AgentQueryResponse,
    AgentResponse,
    AgentSourceItem,
    QueryIntent,
    VALID_QUERY_INTENTS,
)


class TestAgentModels:
    def test_agent_query_request_valid(self) -> None:
        req = AgentQueryRequest(
            project_id="proj-101",
            query="What did the client approve?",
            use_llm=False,
        )
        assert req.project_id == "proj-101"
        assert req.query == "What did the client approve?"
        assert req.use_llm is False

    def test_agent_query_request_default_use_llm_is_false(self) -> None:
        req = AgentQueryRequest(
            project_id="proj-101",
            query="What did the client approve?",
        )
        assert req.use_llm is False

    def test_agent_query_request_extra_fields_forbidden(self) -> None:
        with pytest.raises(ValidationError):
            AgentQueryRequest(
                project_id="proj-101",
                query="Query",
                extra_field="disallowed",  # type: ignore[call-arg]
            )

    def test_agent_query_request_blank_rejected(self) -> None:
        with pytest.raises(ValidationError):
            AgentQueryRequest(project_id="  ", query="Valid query")
        with pytest.raises(ValidationError):
            AgentQueryRequest(project_id="valid-id", query="   ")

    def test_agent_source_item_valid(self) -> None:
        src = AgentSourceItem(
            memory_id="mem-1",
            item_type="task",
            source_id="src-1",
            communication_id="comm-1",
            title="Send structural drawing",
            evidence="Architect will send drawing.",
            score=25.0,
        )
        assert src.title == "Send structural drawing"
        assert src.score == 25.0

    def test_agent_response_valid(self) -> None:
        res = AgentResponse(
            project_id="proj-101",
            query="What did the client approve?",
            intent="approval",
            answer="The client approved the revised kitchen layout.",
            grounded=True,
            result_count=1,
            sources=[
                AgentSourceItem(
                    memory_id="mem-1",
                    item_type="approval",
                    source_id="dec-1",
                    communication_id="comm-1",
                    title="Client approved layout",
                    evidence="Client approved layout.",
                    score=15.0,
                )
            ],
        )
        assert res.grounded is True
        assert res.intent == "approval"
        assert res.result_count == 1
        assert isinstance(res.generated_at, datetime)

    def test_all_valid_query_intents_accepted(self) -> None:
        for it in VALID_QUERY_INTENTS:
            res = AgentResponse(
                project_id="p-1",
                query="q",
                intent=it,  # type: ignore[arg-type]
                answer="a",
                grounded=True,
                result_count=0,
                sources=[],
            )
            assert res.intent == it
