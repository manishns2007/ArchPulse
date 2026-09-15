"""
ArchScale — Module 9 Live Pipeline Demonstration
Demonstrates end-to-end natural language queries against M8 memory via M9 AgentService.
"""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from app.models.agent import AgentQueryRequest
from app.models.communication import CommunicationRecord, SourceType
from app.models.decision import ExtractedDecision
from app.models.task import StructuredTask
from app.models.understanding import UnderstandingResult
from app.services.agent_service import AgentService
from app.services.memory_service import MemoryService


def run_live_m9_demo() -> None:
    db_path = Path("storage/demo_m9_memory.db")
    if db_path.exists():
        db_path.unlink()

    mem_service = MemoryService(db_path=db_path)
    agent_service = AgentService(memory_service=mem_service)

    project_id = "villa-live-proj"
    comm_id = str(uuid4())

    raw_text = (
        "Client approved the revised kitchen layout.\n"
        "Architect will send the structural drawing by Friday.\n"
        "Britto Sir will review the drawing after it is received."
    )

    print("=" * 75)
    print("ARCHSCALE MODULE 9: AGENTIC PROJECT QUERY & USER INTERACTION DEMONSTRATION")
    print("=" * 75)
    print(f"\n[1] Ingested Live Communication (Project: {project_id}):\n{raw_text}\n")

    # Upstream Models
    comm = CommunicationRecord(
        project_id=project_id,
        communication_id=comm_id,
        source_type=SourceType.text,
        raw_content=raw_text,
    )
    und = UnderstandingResult(
        project_id=project_id,
        communication_id=comm_id,
        concise_summary="Client approved kitchen layout; structural drawing to be sent and reviewed.",
        detailed_summary="The client approved the kitchen layout. Architect sends drawing by Friday. Britto Sir reviews.",
        topics=["kitchen layout", "structural drawing", "drawing review"],
        stakeholders=["Client", "Architect", "Britto Sir"],
        communication_type="mixed",
        important_context=["Review scheduled after receipt."],
    )
    dec = ExtractedDecision(
        decision_id="dec-live-kitchen",
        item_type="approval",
        description="Client approved the revised kitchen layout.",
        subject="kitchen layout",
        status="approved",
        evidence="Client approved the revised kitchen layout.",
        confidence=0.99,
    )
    task1 = StructuredTask(
        task_id=uuid4(),
        project_id=project_id,
        communication_id=comm_id,
        action_id="act-live-structural",
        title="Send the structural drawing",
        description="Architect will send the structural drawing by Friday.",
        responsible_party="Architect",
        responsibility_type="role",
        deadline="Friday",
        deadline_type="relative_day",
        normalized_deadline="2026-09-18",
        status="pending",
        priority="high",
        evidence="Architect will send the structural drawing by Friday.",
        decision_context=["Client approved the revised kitchen layout."],
    )
    task2 = StructuredTask(
        task_id=uuid4(),
        project_id=project_id,
        communication_id=comm_id,
        action_id="act-live-britto",
        title="Review the drawing",
        description="Britto Sir will review the drawing after it is received.",
        responsible_party="Britto Sir",
        responsibility_type="person",
        deadline="after it is received",
        deadline_type="event_based",
        status="pending",
        priority="medium",
        evidence="Britto Sir will review the drawing after it is received.",
    )

    # Index into Module 8
    indexed = mem_service.index_project(
        project_id=project_id,
        communications=[comm],
        understandings=[und],
        decisions=[dec],
        tasks=[task1, task2],
        communication_id=comm_id,
    )
    print(f"[2] Indexed {len(indexed)} entities into M8 Project Memory.")

    # Demonstration queries
    queries = [
        "What did the client approve?",
        "What does the architect need to do?",
        "What tasks are assigned to Britto Sir?",
        "What is due this week?",
        "Show me decisions about the kitchen.",
        "Give me the current project status.",
        "What is the status of the swimming pool?",  # Zero hallucination query
    ]

    print("\n" + "=" * 75)
    print("NATURAL LANGUAGE AGENT QUERIES & GROUNDED RESPONSES")
    print("=" * 75)

    for q in queries:
        print(f"\nUser Query: \"{q}\"")
        res = agent_service.query(AgentQueryRequest(project_id=project_id, query=q))
        print(f"Intent: [{res.intent.upper()}] | Grounded: {res.grounded} | Sources Count: {res.result_count}")
        print("-" * 50)
        print("Answer:")
        print(res.answer)
        if res.sources:
            print("\nProvenance Sources:")
            for s in res.sources[:2]:
                print(f"  • [{s.item_type}] {s.title} (comm: {s.communication_id})")
        print("-" * 50)

    # Cleanup demo db
    if db_path.exists():
        db_path.unlink()


if __name__ == "__main__":
    run_live_m9_demo()
