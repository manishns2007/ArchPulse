"""
Live Gemini End-to-End verification script for Module 7:
Ingestion -> M2 Understanding -> M3 Action -> M4 Responsibility -> M5 Deadline -> M6 Decision -> M7 Task
"""

import json
from fastapi.testclient import TestClient
from app.main import app

def main() -> None:
    client = TestClient(app)
    
    text = (
        "Client approved the revised kitchen layout. "
        "Architect will send the structural drawing by Friday. "
        "Britto Sir will review the drawing after it is received."
    )
    print("--- 1. Ingesting Communication ---")
    ingest_resp = client.post(
        "/api/v1/ingest/text",
        json={
            "project_id": "villa-live-proj",
            "source_type": "text",
            "content": text,
        },
    )
    assert ingest_resp.status_code == 201, ingest_resp.text
    ingest_data = ingest_resp.json()["data"]
    comm_id = ingest_data["communication_id"]
    print(f"Ingested Communication ID: {comm_id}")
    
    print("\n--- 2. Structuring Tasks via Module 7 (Chaining M2-M6 Live with Gemini) ---")
    task_resp = client.post(
        "/api/v1/tasks/structure",
        json={
            "communication_id": comm_id,
            "include_understanding_context": True,
        },
    )
    assert task_resp.status_code == 200, task_resp.text
    structured_result = task_resp.json()
    print("\n=== LIVE GEMINI STRUCTURED TASK RESULT ===")
    print(json.dumps(structured_result, indent=2))

if __name__ == "__main__":
    main()
