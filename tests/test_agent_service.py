"""
ArchScale — Module 9: Agentic Project Query & User Interaction
Unit tests for AgentService: intent routing, M8 coordination, evidence grounding,
zero-hallucination guarantee, and provenance.
"""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

from app.models.agent import AgentQueryRequest
from app.models.communication import CommunicationRecord, SourceType
from app.models.decision import ExtractedDecision
from app.models.task import StructuredTask
from app.models.understanding import UnderstandingResult
from app.services.agent_service import AgentService, UNGROUNDED_MESSAGE
from app.services.memory_service import MemoryService


@pytest.fixture()
def memory_service(tmp_path: Path) -> MemoryService:
    """Provide isolated MemoryService."""
    return MemoryService(db_path=tmp_path / "agent_test_memory.db")


@pytest.fixture()
def agent_service(memory_service: MemoryService) -> AgentService:
    """Provide AgentService wired to the isolated MemoryService."""
    return AgentService(memory_service=memory_service)


# ---------------------------------------------------------------------------
# Routing Tests
# ---------------------------------------------------------------------------


class TestAgentQueryRouting:
    def test_route_approval_queries(self, agent_service: AgentService) -> None:
        intent, _ = agent_service.route_query("What did the client approve?")
        assert intent == "approval"

        intent2, _ = agent_service.route_query("Show me all approvals.")
        assert intent2 == "approval"

    def test_route_decision_queries(self, agent_service: AgentService) -> None:
        intent, _ = agent_service.route_query("Show me decisions about the kitchen.")
        assert intent == "decision"

        intent2, _ = agent_service.route_query("What was decided regarding the foundation?")
        assert intent2 == "decision"

    def test_route_responsibility_and_task_queries(self, agent_service: AgentService) -> None:
        intent, filters = agent_service.route_query("What does the architect need to do?")
        assert intent in ("task", "responsibility")
        assert filters.get("responsible_party") == "Architect"

        intent2, filters2 = agent_service.route_query("What tasks are assigned to Britto Sir?")
        assert intent2 in ("task", "responsibility")
        assert filters2.get("responsible_party") == "Britto Sir"

    def test_route_deadline_queries(self, agent_service: AgentService) -> None:
        intent, _ = agent_service.route_query("What is due this week?")
        assert intent == "deadline"

        intent2, _ = agent_service.route_query("What deadlines are coming up?")
        assert intent2 == "deadline"

    def test_route_project_overview(self, agent_service: AgentService) -> None:
        intent, _ = agent_service.route_query("Give me the current project status.")
        assert intent == "project_overview"

        intent2, _ = agent_service.route_query("Show project overview.")
        assert intent2 == "project_overview"

    def test_route_communication_queries(self, agent_service: AgentService) -> None:
        intent, _ = agent_service.route_query("What communication mentioned the structural drawing?")
        assert intent == "communication"

    def test_route_general_memory_fallback(self, agent_service: AgentService) -> None:
        intent, _ = agent_service.route_query("Tell me about the staircase.")
        assert intent == "general_memory"


# ---------------------------------------------------------------------------
# Zero Hallucination Tests
# ---------------------------------------------------------------------------


class TestZeroHallucination:
    def test_empty_memory_returns_ungrounded_fallback(self, agent_service: AgentService) -> None:
        req = AgentQueryRequest(
            project_id="empty-proj",
            query="What did the client approve?",
        )
        res = agent_service.query(req)
        assert res.grounded is False
        assert res.result_count == 0
        assert len(res.sources) == 0
        assert res.answer == UNGROUNDED_MESSAGE

    def test_unmatched_query_returns_ungrounded_fallback(
        self,
        memory_service: MemoryService,
        agent_service: AgentService,
    ) -> None:
        # Index one task about plumbing
        memory_service.index_task(
            StructuredTask(
                project_id="plumbing-proj",
                communication_id="comm-p",
                action_id="act-p",
                title="Install PVC pipe",
                description="Install PVC pipes in basement.",
                evidence="Install PVC pipe.",
            )
        )
        req = AgentQueryRequest(
            project_id="plumbing-proj",
            query="What was approved regarding the swimming pool?",
        )
        res = agent_service.query(req)
        assert res.grounded is False
        assert res.result_count == 0
        assert res.answer == UNGROUNDED_MESSAGE


# ---------------------------------------------------------------------------
# Grounded Answer & Provenance Tests
# ---------------------------------------------------------------------------


class TestGroundedAnswerSynthesis:
    @pytest.fixture(autouse=True)
    def setup_project_memory(self, memory_service: MemoryService) -> None:
        self.project_id = "villa-agent-test"
        self.comm_id = "comm-agent-001"

        # Index Communication
        comm = CommunicationRecord(
            project_id=self.project_id,
            communication_id=self.comm_id,
            source_type=SourceType.text,
            raw_content=(
                "Client approved the revised kitchen layout.\n"
                "Architect will send the structural drawing by Friday.\n"
                "Britto Sir will review the drawing after it is received."
            ),
        )
        memory_service.index_communication(comm)

        # Index Approval
        appr = ExtractedDecision(
            decision_id="dec-agent-kitchen",
            item_type="approval",
            description="Client approved the revised kitchen layout.",
            subject="kitchen layout",
            status="approved",
            evidence="Client approved the revised kitchen layout.",
            confidence=0.99,
        )
        memory_service.index_decision(appr, self.project_id, self.comm_id)

        # Index Structural task
        task_struct = StructuredTask(
            task_id=uuid4(),
            project_id=self.project_id,
            communication_id=self.comm_id,
            action_id="act-struct",
            title="Send the structural drawing",
            description="Architect will send the structural drawing by Friday.",
            responsible_party="Architect",
            responsibility_type="role",
            deadline="Friday",
            normalized_deadline="2026-09-18",
            status="pending",
            evidence="Architect will send the structural drawing by Friday.",
        )
        memory_service.index_task(task_struct)

        # Index Britto review task
        task_britto = StructuredTask(
            task_id=uuid4(),
            project_id=self.project_id,
            communication_id=self.comm_id,
            action_id="act-britto",
            title="Review the drawing",
            description="Britto Sir will review the drawing after it is received.",
            responsible_party="Britto Sir",
            responsibility_type="person",
            deadline="after it is received",
            status="pending",
            evidence="Britto Sir will review the drawing after it is received.",
        )
        memory_service.index_task(task_britto)

    def test_query_what_did_client_approve(self, agent_service: AgentService) -> None:
        req = AgentQueryRequest(
            project_id=self.project_id,
            query="What did the client approve?",
        )
        res = agent_service.query(req)

        assert res.grounded is True
        assert res.result_count >= 1
        assert "kitchen layout" in res.answer.lower()
        assert "Client approved the revised kitchen layout." in res.answer
        assert len(res.sources) >= 1
        top_src = res.sources[0]
        assert top_src.item_type == "approval"
        assert top_src.communication_id == self.comm_id
        assert top_src.evidence == "Client approved the revised kitchen layout."

    def test_query_architect_tasks(self, agent_service: AgentService) -> None:
        req = AgentQueryRequest(
            project_id=self.project_id,
            query="What does the architect need to do?",
        )
        res = agent_service.query(req)

        assert res.grounded is True
        assert "structural drawing" in res.answer.lower()
        assert "2026-09-18" in res.answer or "Friday" in res.answer
        assert any("Architect will send the structural drawing" in (s.evidence or "") for s in res.sources)

    def test_query_britto_sir(self, agent_service: AgentService) -> None:
        req = AgentQueryRequest(
            project_id=self.project_id,
            query="What tasks are assigned to Britto Sir?",
        )
        res = agent_service.query(req)

        assert res.grounded is True
        assert "Review the drawing" in res.answer
        assert any("Britto Sir will review the drawing" in (s.evidence or "") for s in res.sources)

    def test_query_project_overview(self, agent_service: AgentService) -> None:
        req = AgentQueryRequest(
            project_id=self.project_id,
            query="Give me the current project status.",
        )
        res = agent_service.query(req)

        assert res.grounded is True
        assert res.intent == "project_overview"
        assert "Project Overview" in res.answer
        assert "Total Memory Items" in res.answer
        assert res.result_count >= 1

    def test_strict_project_isolation(
        self,
        memory_service: MemoryService,
        agent_service: AgentService,
    ) -> None:
        # Index secret item in Project B
        memory_service.index_task(
            StructuredTask(
                project_id="classified-b",
                communication_id="comm-b",
                action_id="act-b",
                title="Classified nuclear silo inspection",
                description="Top secret.",
                evidence="Classified nuclear silo inspection.",
            )
        )

        # Query in villa project about nuclear silo
        req = AgentQueryRequest(
            project_id=self.project_id,
            query="What are the details of the nuclear silo inspection?",
        )
        res = agent_service.query(req)

        assert res.grounded is False
        assert res.result_count == 0
        assert res.answer == UNGROUNDED_MESSAGE
