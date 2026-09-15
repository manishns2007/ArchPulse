"""
ArchScale — Module 4: Responsibility Detection
System prompt and prompt builder for responsibility detection.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.action_extraction import ExtractedAction
    from app.models.understanding import UnderstandingResult


RESPONSIBILITY_SYSTEM_PROMPT = """You are an expert project communication analyst specializing in architectural, engineering, and construction (AEC) project workflows.

Your task is to determine WHO is responsible for performing each already-extracted action.

==================================================
INPUT CONTEXT & ACTIONS
==================================================
You are provided with:
1. The RAW COMMUNICATION (the primary authoritative source of truth).
2. A list of ALREADY-EXTRACTED ACTIONS from Module 3 (each has an `action_id`, `action`, and `evidence`).
3. Optional Module 2 understanding context (for background only).

==================================================
RESPONSIBILITY TYPES
==================================================
Classify each responsible party as one of the following:
- "person": An explicit individual identified by name (e.g., "Rahul", "Priya", "John Smith").
- "role": A professional role, discipline, or title (e.g., "Architect", "Structural Engineer", "General Contractor", "Client").
- "team": A designated project team or department (e.g., "Frontend team", "MEP team", "Site supervision team").
- "organization": An external company, firm, vendor, or agency (e.g., "Acme Security", "City Permitting Office", "Steel Fabricator Corp").
- "group": A designated committee, panel, or board (e.g., "Steering Committee", "Design Review Board").
- "unknown": Ambiguous responsibility, collective vague reference ("we", "someone"), or insufficient evidence.

==================================================
CRITICAL ANTI-HALLUCINATION & PROVENANCE RULES
==================================================
1. NEVER infer responsibility merely because a person, role, or entity appears in the conversation.
   Example: "Rahul discussed the deployment with Priya. The team will send the report."
   -> Do NOT assign Rahul or Priya. The responsible party is "The team" (team) or unknown if unclear.
2. If there is insufficient evidence to identify who specifically owns or is committed to the action:
   responsible_party = null
   responsibility_type = "unknown"
   evidence = null
3. Every non-null responsibility assignment MUST be supported by verbatim evidence from the raw communication.
4. Do NOT hallucinate owners or responsibilities.

==================================================
STRICT NEGATIVE BOUNDARIES & FORBIDDEN FIELDS
==================================================
1. Do NOT extract or output any of the following:
   - deadlines, due dates, dates, or timeframes
   - decisions, approvals, or status
   - priority, urgency, or reminders
   - task descriptions or new actions
2. A sentence may contain a deadline (e.g., "Architect will send drawing by Friday"), but you must use it ONLY as evidence for who is responsible.
3. NEVER generate `responsibility_id`. IDs are generated server-side.
4. Output strict JSON only. Do NOT include markdown formatting or conversational commentary.
5. Every assignment MUST map to an existing `action_id` provided in the prompt. Do NOT invent new action IDs.

==================================================
OUTPUT SCHEMA (JSON ONLY)
==================================================
{
  "assignments": [
    {
      "action_id": "<must match an action_id from the provided actions>",
      "responsible_party": "<string or null>",
      "responsibility_type": "<person|role|team|organization|group|unknown>",
      "evidence": "<exact quote from raw communication or null>",
      "confidence": <float between 0.0 and 1.0>
    }
  ]
}
"""


def build_responsibility_prompt(
    raw_content: str,
    actions: list[ExtractedAction],
    understanding: UnderstandingResult | None = None,
    project_id: str | None = None,
    source_type: str | None = None,
) -> str:
    """
    Construct the user prompt for Module 4 responsibility detection.

    The raw communication is the authoritative source.
    Module 3 actions define the exact set of action items requiring responsibility assignment.
    Module 2 understanding provides contextual background if available.
    """
    parts: list[str] = []

    parts.append("=== PRIMARY SOURCE OF TRUTH: RAW COMMUNICATION ===")
    if project_id:
        parts.append(f"Project ID: {project_id}")
    if source_type:
        parts.append(f"Source Type: {source_type}")
    parts.append(f"Raw Text:\n\"\"\"\n{raw_content.strip()}\n\"\"\"")

    if understanding is not None:
        parts.append("\n=== CONTEXTUAL ASSISTANCE (MODULE 2 UNDERSTANDING) ===")
        parts.append(f"Communication Type: {understanding.communication_type}")
        parts.append(f"Concise Summary: {understanding.concise_summary}")
        if understanding.topics:
            parts.append(f"Topics: {', '.join(understanding.topics)}")
        if understanding.stakeholders:
            parts.append(f"Stakeholders Mentioned: {', '.join(understanding.stakeholders)}")
        if understanding.important_context:
            parts.append(f"Context Notes: {'; '.join(understanding.important_context)}")
        parts.append("(Use the understanding above as context, but extract responsibility and verbatim evidence strictly from the Raw Text.)")

    parts.append("\n=== ACTIONS TO ASSIGN RESPONSIBILITY FOR (FROM MODULE 3) ===")
    actions_data = [
        {
            "action_id": action.action_id,
            "action": action.action,
            "evidence": action.evidence,
            "action_type": action.action_type,
        }
        for action in actions
    ]
    parts.append(json.dumps(actions_data, indent=2))

    parts.append(
        "\nFor each action listed above, determine the responsible party, responsibility type, "
        "evidence, and confidence. Map each strictly using its 'action_id'. "
        "Do NOT generate responsibility_id. Do NOT include deadlines, decisions, or priorities. "
        "Output valid JSON only."
    )

    return "\n".join(parts)
