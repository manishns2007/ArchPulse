"""
ArchScale — Module 9: Agentic Project Query & User Interaction
Core service: routes user queries, coordinates Module 8 memory retrieval,
and synthesizes evidence-grounded answers with full provenance.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from app.llm.provider import FakeLLMProvider, LLMProvider, create_provider
from app.models.agent import (
    AgentQueryRequest,
    AgentResponse,
    AgentSourceItem,
    QueryIntent,
)
from app.models.memory import MemorySearchRequest, MemorySearchResultItem
from app.services.memory_service import MemoryService

logger = logging.getLogger(__name__)

# Fallback message for ungrounded queries
UNGROUNDED_MESSAGE = "I couldn't find evidence for that in this project's communication history."

# Common role/person entity keywords for deterministic extraction
KNOWN_ENTITIES: dict[str, str] = {
    "architect": "Architect",
    "britto sir": "Britto Sir",
    "britto": "Britto Sir",
    "client": "Client",
    "engineer": "Engineer",
    "structural engineer": "Structural Engineer",
    "contractor": "Contractor",
    "electrician": "Electrician",
    "plumber": "Plumber",
    "developer": "Developer",
}


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class AgentService:
    """
    Agentic orchestration layer: understands user queries, queries M8 Project Memory,
    and formats evidence-backed responses.
    """

    def __init__(
        self,
        memory_service: MemoryService | None = None,
        llm_provider: LLMProvider | None = None,
    ) -> None:
        self.memory_service = memory_service or MemoryService()
        self.llm_provider = llm_provider or FakeLLMProvider()

    # -----------------------------------------------------------------------
    # Deterministic Query Intent Routing
    # -----------------------------------------------------------------------

    def route_query(self, query: str) -> tuple[QueryIntent, dict[str, Any]]:
        """
        Inspect query text and determine primary intent and any entity filters.
        Deterministic-first: handles common project query patterns without LLM.
        """
        q_lower = query.strip().lower()
        filters: dict[str, Any] = {}

        # 1. Detect entity (responsible_party)
        for keyword, canonical_name in KNOWN_ENTITIES.items():
            if re.search(r"\b" + re.escape(keyword) + r"\b", q_lower):
                filters["responsible_party"] = canonical_name
                break

        # 2. Detect status filter
        if "completed" in q_lower or "done" in q_lower:
            filters["status"] = "completed"
        elif "pending" in q_lower or "waiting" in q_lower:
            filters["status"] = "pending"
        elif "blocked" in q_lower:
            filters["status"] = "blocked"

        # 3. Intent classification based on keywords/patterns
        # Project Overview intent
        if any(p in q_lower for p in ("project overview", "project status", "summary of the project", "current project status")):
            return "project_overview", filters

        # Approval intent
        if any(w in q_lower for w in ("approve", "approved", "approval", "approvals")):
            return "approval", filters

        # Decision intent
        if any(w in q_lower for w in ("decision", "decisions", "decided", "choice", "conclude")):
            return "decision", filters

        # Deadline intent
        if any(w in q_lower for w in ("due", "deadline", "deadlines", "due date", "when is")):
            return "deadline", filters

        # Responsibility intent
        if any(
            p in q_lower
            for p in (
                "assigned to",
                "assigned for",
                "assigned",
                "assignee",
                "assignment",
                "responsible for",
                "responsibility",
                "who is",
                "who has",
                "who was",
                "who will",
                "who owns",
                "who handles",
                "who is handling",
                "who leads",
                "in charge",
                "took charge",
                "waiting for",
            )
        ):
            return "responsibility", filters

        # Task intent
        if any(w in q_lower for w in ("task", "tasks", "action", "actions", "need to do", "deliverable", "deliverables", "pending")):
            return "task", filters

        # Communication intent
        if any(w in q_lower for w in ("communication", "transcript", "email", "notes", "mentioned in", "what conversation")):
            return "communication", filters

        # Default fallback
        return "general_memory", filters

    # -----------------------------------------------------------------------
    # Query Execution & Response Generation
    # -----------------------------------------------------------------------

    def query(self, request: AgentQueryRequest) -> AgentResponse:
        """
        Main query entry point: routes intent, retrieves from M8, and constructs
        strictly evidence-grounded answer with complete provenance.
        """
        project_id = request.project_id.strip()
        query_text = request.query.strip()

        intent, filters = self.route_query(query_text)

        # 1. Project Overview Intent
        if intent == "project_overview":
            return self._handle_project_overview(project_id, query_text)

        # 2. Memory Retrieval via M8
        results = self._retrieve_from_m8(project_id, query_text, intent, filters)

        # Filter out low-relevance noise if top item has a strong match
        if results and results[0].score and results[0].score >= 10.0:
            min_threshold = max(results[0].score * 0.45, 8.0)
            strong_results = [r for r in results if (r.score or 0.0) >= min_threshold]
            if strong_results:
                results = strong_results

        # 3. Zero-Hallucination check: No supporting evidence found
        if not results:
            return AgentResponse(
                project_id=project_id,
                query=query_text,
                intent=intent,
                answer=UNGROUNDED_MESSAGE,
                grounded=False,
                result_count=0,
                sources=[],
                generated_at=datetime.now(timezone.utc),
            )

        # 4. Map M8 results to provenance sources
        sources: list[AgentSourceItem] = [
            AgentSourceItem(
                memory_id=r.memory_id,
                item_type=r.item_type,
                source_id=r.source_id,
                communication_id=r.communication_id,
                title=r.title,
                evidence=r.evidence,
                score=r.score,
            )
            for r in results
        ]

        # 5. Synthesize grounded answer
        answer = self._synthesize_grounded_answer(
            query=query_text,
            intent=intent,
            results=results,
            use_llm=request.use_llm,
        )

        return AgentResponse(
            project_id=project_id,
            query=query_text,
            intent=intent,
            answer=answer,
            grounded=True,
            result_count=len(sources),
            sources=sources,
            generated_at=datetime.now(timezone.utc),
        )

    # -----------------------------------------------------------------------
    # Internal Retrieval Orchestrator
    # -----------------------------------------------------------------------

    def _retrieve_from_m8(
        self,
        project_id: str,
        query: str,
        intent: QueryIntent,
        filters: dict[str, Any],
    ) -> list[MemorySearchResultItem]:
        """Execute retrieval exclusively through M8 MemoryService."""
        # Clean query for search
        search_kw = query

        # Search with intent-specific item_type if appropriate
        item_type_filter = None
        if intent == "approval":
            item_type_filter = "approval"
        elif intent == "decision":
            item_type_filter = "decision"
        elif intent in ("task", "responsibility", "deadline"):
            item_type_filter = "task"
        elif intent == "communication":
            item_type_filter = "communication"

        resp_party = (
            filters.get("responsible_party")
            if intent in ("task", "responsibility")
            else None
        )

        search_req = MemorySearchRequest(
            project_id=project_id,
            query=search_kw,
            item_type=item_type_filter,  # type: ignore[arg-type]
            responsible_party=resp_party,
            status=filters.get("status"),
            limit=10,
        )
        res = self.memory_service.search(search_req)

        # If specific item_type search returned 0, fallback to general search
        if res.result_count == 0 and item_type_filter is not None:
            fallback_req = MemorySearchRequest(
                project_id=project_id,
                query=search_kw,
                limit=10,
            )
            res = self.memory_service.search(fallback_req)

        # If deadline query returned no keyword matches, retrieve tasks with deadlines
        if intent == "deadline" and res.result_count == 0:
            tasks_data = self.memory_service.get_project_tasks(project_id)
            deadline_tasks = [
                t for t in tasks_data.tasks
                if (t.deadline or t.normalized_deadline) and t.deadline_type != "no_deadline"
            ]
            if deadline_tasks:
                return [
                    MemorySearchResultItem(
                        memory_id=str(t.task_id),
                        project_id=t.project_id,
                        item_type="task",
                        source_id=str(t.task_id),
                        communication_id=str(t.communication_id),
                        title=t.title,
                        content=t.description,
                        evidence=t.evidence,
                        metadata={
                            "responsible_party": t.responsible_party,
                            "deadline": t.deadline,
                            "normalized_deadline": t.normalized_deadline,
                            "status": t.status,
                        },
                        score=10.0,
                        retrieval_mode="keyword",
                    )
                    for t in deadline_tasks
                ]

        return res.results

    def _handle_project_overview(self, project_id: str, query: str) -> AgentResponse:
        """Handle project overview requests via M8 get_project_memory."""
        overview = self.memory_service.get_project_memory(project_id)
        if overview.memory_items == 0:
            return AgentResponse(
                project_id=project_id,
                query=query,
                intent="project_overview",
                answer=UNGROUNDED_MESSAGE,
                grounded=False,
                result_count=0,
                sources=[],
                generated_at=datetime.now(timezone.utc),
            )

        # Fetch recent general items for provenance
        recent_search = self.memory_service.search(
            MemorySearchRequest(project_id=project_id, query="", limit=5)
        )
        sources = [
            AgentSourceItem(
                memory_id=r.memory_id,
                item_type=r.item_type,
                source_id=r.source_id,
                communication_id=r.communication_id,
                title=r.title,
                evidence=r.evidence,
                score=r.score,
            )
            for r in recent_search.results
        ]

        answer = (
            f"Project Overview for '{project_id}':\n\n"
            f"• Total Memory Items: {overview.memory_items}\n"
            f"• Communications Ingested: {overview.communications}\n"
            f"• Structured Tasks: {overview.tasks}\n"
            f"• Confirmed Decisions: {overview.decisions}\n"
            f"• Explicit Approvals: {overview.approvals}"
        )

        return AgentResponse(
            project_id=project_id,
            query=query,
            intent="project_overview",
            answer=answer,
            grounded=True,
            result_count=len(sources),
            sources=sources,
            generated_at=datetime.now(timezone.utc),
        )

    # -----------------------------------------------------------------------
    # Grounded Answer Synthesis (Zero Hallucination)
    # -----------------------------------------------------------------------

    def _synthesize_grounded_answer(
        self,
        query: str,
        intent: QueryIntent,
        results: list[MemorySearchResultItem],
        use_llm: bool = False,
    ) -> str:
        """
        Synthesize answer exclusively using retrieved M8 evidence.
        Deterministic synthesis by default; strictly constrained if LLM is enabled.
        """
        if not results:
            return UNGROUNDED_MESSAGE

        # If LLM requested and available (and not FakeLLMProvider)
        if use_llm and not isinstance(self.llm_provider, FakeLLMProvider):
            evidence_context = "\n---\n".join([
                f"Title: {r.title}\nType: {r.item_type}\nContent: {r.content}\n"
                f"Evidence: {r.evidence or 'None'}\nMetadata: {r.metadata}"
                for r in results[:5]
            ])
            prompt = (
                "You are an assistant answering a project question strictly and exclusively "
                "based on the verified memory items provided below. Do NOT invent, assume, or extrapolate "
                "any facts, dates, people, or tasks not present in the evidence.\n\n"
                f"Question: {query}\n\n"
                f"Verified Memory Items:\n{evidence_context}\n\n"
                "Provide a direct, concise, factual answer addressing specifically what was asked. "
                "Include the responsible person and exact quote evidence where applicable. "
                "Do not include unrelated meeting notes or background discussions."
            )
            try:
                llm_response = self.llm_provider.generate(prompt)
                if llm_response and llm_response.text.strip():
                    return llm_response.text.strip()
            except Exception as exc:
                logger.warning("LLM synthesis failed, falling back to deterministic: %s", exc)

        # Deterministic Grounded Synthesis
        # 1. Approval synthesis
        if intent == "approval" or results[0].item_type == "approval":
            top = results[0]
            desc = top.content
            evidence_text = f'\n\nEvidence:\n"{top.evidence}"' if top.evidence else ""
            source_text = f"\n\nSource:\ncommunication {top.communication_id}"
            return f"{desc}{evidence_text}{source_text}"

        # 2. Task / Responsibility / Deadline synthesis
        if intent in ("task", "responsibility", "deadline") or results[0].item_type == "task":
            task_items = [r for r in results if r.item_type == "task"]
            if not task_items:
                task_items = results[:3]

            party = task_items[0].metadata.get("responsible_party")
            all_same_party = bool(party) and all(
                t.metadata.get("responsible_party") == party for t in task_items
            )
            if party and all_same_party:
                party_header = f"{party} is assigned to the following task(s):"
            elif party:
                party_header = f"Tasks assigned to {party} and others:"
            else:
                party_header = "Retrieved task(s):"

            task_bullets: list[str] = []
            evidences: list[str] = []
            for t in task_items[:5]:
                owner = t.metadata.get("responsible_party")
                dl = t.metadata.get("normalized_deadline") or t.metadata.get("deadline")
                status = t.metadata.get("status")

                details = []
                if owner and not (party and all_same_party):
                    details.append(f"Owner: {owner}")
                if dl:
                    details.append(f"Due: {dl}")
                if status:
                    details.append(f"Status: {status}")

                details_str = f" ({', '.join(details)})" if details else ""
                task_bullets.append(f"• {t.title}{details_str}")
                if t.evidence and f'"{t.evidence}"' not in evidences:
                    evidences.append(f'"{t.evidence}"')

            answer_parts = [party_header, "\n".join(task_bullets)]
            if evidences:
                answer_parts.append("Evidence:\n" + "\n".join(evidences[:2]))
            answer_parts.append(f"Source:\ncommunication {task_items[0].communication_id}")
            return "\n\n".join(answer_parts)

        # 3. Decision synthesis
        if intent == "decision" or results[0].item_type == "decision":
            dec_items = [r for r in results if r.item_type in ("decision", "approval")]
            if not dec_items:
                dec_items = results[:3]

            bullets = [f"• {d.title}" for d in dec_items]
            evidences = [f'"{d.evidence}"' for d in dec_items if d.evidence]

            answer_parts = ["Decisions recorded for the project:", "\n".join(bullets)]
            if evidences:
                answer_parts.append(f"Evidence:\n" + "\n".join(evidences[:2]))
            answer_parts.append(f"Source:\ncommunication {dec_items[0].communication_id}")
            return "\n\n".join(answer_parts)

        # 4. General Memory / Communication fallback
        top = results[0]
        answer_parts = ["Found relevant project memory:"]
        if top.title:
            answer_parts.append(f"• {top.title}")
        # Only include raw content if it's short and distinct from the title
        if not top.title and top.content:
            answer_parts.append(top.content)
        elif top.content and top.content != top.title and len(top.content) <= 300:
            answer_parts.append(top.content)

        # Include matching structured items if present
        structured_items = [
            r for r in results if r.item_type in ("task", "decision", "approval") and r != top
        ]
        if structured_items:
            extra_bullets = []
            for item in structured_items[:3]:
                owner = item.metadata.get("responsible_party")
                owner_str = f" (Owner: {owner})" if owner else ""
                extra_bullets.append(f"• {item.title}{owner_str}")
            if extra_bullets:
                answer_parts.append("\n".join(extra_bullets))

        if top.evidence:
            answer_parts.append(f'Evidence:\n"{top.evidence}"')
        answer_parts.append(f"Source:\ncommunication {top.communication_id}")
        return "\n\n".join(answer_parts)
