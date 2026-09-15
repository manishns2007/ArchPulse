"""
ArchScale — Module 8 Live Pipeline & Search Demonstration Script
Demonstrates M1 -> M2 -> M6 -> M7 -> M8 index -> M8 search with required queries.
"""

from __future__ import annotations

import json
from uuid import uuid4
from pathlib import Path

from app.models.communication import CommunicationRecord, SourceType
from app.models.decision import ExtractedDecision
from app.models.memory import MemorySearchRequest
from app.models.task import StructuredTask
from app.models.understanding import UnderstandingResult
from app.services.memory_service import MemoryService


def run_live_demonstration() -> None:
    db_path = Path("storage/demo_memory.db")
    if db_path.exists():
        db_path.unlink()

    service = MemoryService(db_path=db_path)

    project_id = "villa-live-proj"
    comm_id = str(uuid4())

    raw_text = (
        "Client approved the revised kitchen layout.\n"
        "Architect will send the structural drawing by Friday.\n"
        "Britto Sir will review the drawing after it is received."
    )

    print("=" * 70)
    print("ARCHSCALE MODULE 8: PROJECT MEMORY / SEARCHABLE MEMORY DEMONSTRATION")
    print("=" * 70)
    print(f"\n[1] Source Communication (Project: {project_id}):\n{raw_text}\n")

    # Upstream Models
    comm = CommunicationRecord(
        project_id=project_id,
        communication_id=comm_id,
        source_type=SourceType.text,
        raw_content=raw_text,
    )
    understanding = UnderstandingResult(
        project_id=project_id,
        communication_id=comm_id,
        concise_summary="Client approved kitchen layout; structural drawing to be sent and reviewed.",
        detailed_summary=(
            "The client approved the revised kitchen layout. "
            "The architect will send the structural drawing by Friday, "
            "and Britto Sir will review it after receipt."
        ),
        topics=["kitchen layout", "structural drawing", "drawing review"],
        stakeholders=["Client", "Architect", "Britto Sir"],
        communication_type="mixed",
        important_context=["Review scheduled after receipt."],
    )
    decision = ExtractedDecision(
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
    indexed = service.index_project(
        project_id=project_id,
        communications=[comm],
        understandings=[understanding],
        decisions=[decision],
        tasks=[task1, task2],
        communication_id=comm_id,
    )
    print(f"[2] Indexed {len(indexed)} entities into Project Memory:")
    for item in indexed:
        print(f"    - [{item.item_type.upper()}] {item.title} (source_id: {item.source_id})")

    # Index decoy item for another project
    service.index_task(
        StructuredTask(
            project_id="other-secret-project",
            communication_id="comm-other",
            action_id="act-other",
            title="Send the structural drawing for secret bunker",
            description="Confidential blueprints.",
            responsible_party="Architect",
            evidence="Secret bunker.",
        )
    )

    # Queries
    queries = [
        "What did the client approve?",
        "structural drawing",
        "Britto Sir",
        "What tasks are assigned to the architect?",
    ]

    print("\n" + "=" * 70)
    print("SEARCH & RETRIEVAL DEMONSTRATION")
    print("=" * 70)

    for q in queries:
        print(f"\n>>> Query: \"{q}\"")
        res = service.search(MemorySearchRequest(project_id=project_id, query=q))
        print(f"Results Count: {res.result_count} | Retrieval Mode: {res.retrieval_mode}")
        for idx, r in enumerate(res.results[:2], 1):
            print(f"  Result #{idx} (Score: {r.score}) [{r.item_type}]:")
            print(f"    Title: {r.title}")
            print(f"    Content: {r.content}")
            print(f"    Evidence: \"{r.evidence}\"")
            print(f"    Provenance: communication_id={r.communication_id} | source_id={r.source_id}")
            if "responsible_party" in r.metadata:
                print(f"    Owner: {r.metadata.get('responsible_party')} | Deadline: {r.metadata.get('normalized_deadline') or r.metadata.get('deadline')}")

    # Project Isolation Check
    print("\n" + "=" * 70)
    print("PROJECT ISOLATION DEMONSTRATION")
    print("=" * 70)
    iso_query = "secret bunker"
    print(f">>> Query in '{project_id}': \"{iso_query}\"")
    iso_res = service.search(MemorySearchRequest(project_id=project_id, query=iso_query))
    print(f"Results Count: {iso_res.result_count} (Must be 0)")
    assert iso_res.result_count == 0, "Isolation failure!"
    print("[PASS] Strict project isolation verified: Project A cannot retrieve Project B data.")

    # Clean up demo DB
    if db_path.exists():
        db_path.unlink()


if __name__ == "__main__":
    run_live_demonstration()
