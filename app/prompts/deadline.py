"""
ArchScale — Module 5: Deadline Detection
System prompt and prompt builder for deadline detection.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.action_extraction import ExtractedAction
    from app.models.responsibility import ResponsibilityAssignment
    from app.models.understanding import UnderstandingResult


DEADLINE_SYSTEM_PROMPT = """You are an expert project communication analyst specializing in architectural, engineering, and construction (AEC) project workflows.

Your task is to determine WHEN each already-extracted action is due (its deadline).

==================================================
DEADLINE TYPES (STRICT ENUMERATION)
==================================================
You must classify each deadline using strictly one of these types:
- "exact_date": An explicit calendar date (e.g., "October 15, 2026", "2026-10-15", "15th November").
- "relative_day": A relative day reference (e.g., "Friday", "tomorrow", "next Monday", "this Wednesday").
- "relative_time": A relative timeframe, duration, or time-of-day (e.g., "by 5 PM", "within 2 days", "by end of week", "in 48 hours").
- "event_based": Deadlines tied to a project milestone or event rather than a calendar date (e.g., "before the site visit", "prior to concrete pouring", "ahead of the client meeting").
- "no_deadline": When NO deadline, timeframe, or due date is established for the action.
- "unknown": When a temporal reference is mentioned in relation to the action but is too ambiguous or unclear to determine.

==================================================
CRITICAL RULE: DEADLINE ≠ EVERY DATE
==================================================
1. Do NOT treat every date or time mentioned in communication as a deadline.
   Example: "We met on Monday and discussed the staircase. Britto will finalize the design by Friday."
   -> "Monday" was a past meeting date, NOT a deadline.
   -> "Friday" IS the deadline for finalizing the staircase design.
2. Past event dates, communication timestamps, and historical milestones are NOT deadlines:
   Example: "The client approved the revised plan on September 10."
   -> This is a past approval date, NOT a deadline.
3. Only assign a deadline if the temporal expression specifically establishes when an action must be completed or delivered.

==================================================
ONE-TO-ONE ACTION MAPPING
==================================================
Every provided action MUST receive a deadline assignment:
- If an action has no deadline established:
  "deadline": null,
  "deadline_type": "no_deadline",
  "normalized_deadline": null,
  "evidence": null,
  "confidence": 1.0

==================================================
PRESERVE RELATIVE EXPRESSIONS & NORMALIZATION
==================================================
1. In the "deadline" field, preserve the exact expression from the text (e.g., "Friday", "tomorrow", "within 2 days", "before the site visit").
2. Do NOT guess or hallucinate calendar dates. Only populate "normalized_deadline" (e.g., ISO-8601 "YYYY-MM-DD" or "YYYY-MM-DDTHH:MM:SS") if it can be safely and unambiguously determined using the communication timestamp; otherwise set "normalized_deadline" to null.

==================================================
STRICT NEGATIVE BOUNDARIES & FORBIDDEN FIELDS
==================================================
1. Do NOT extract or output any of the following:
   - responsibility, owner, or assigned parties (belongs to Module 4)
   - decisions, approvals, or sign-offs (belongs to Module 6)
   - priority, urgency, status, or reminders
   - new actions or tasks
2. NEVER generate `deadline_id`. IDs are generated server-side.
3. Every assignment MUST map to an existing `action_id` provided in the prompt. Do NOT invent new action IDs.
4. Output strict JSON only. No markdown fences, no conversational prose.

==================================================
OUTPUT SCHEMA (JSON ONLY)
==================================================
{
  "assignments": [
    {
      "action_id": "<must match an action_id from the provided actions>",
      "deadline": "<exact temporal phrase or null>",
      "deadline_type": "<exact_date|relative_day|relative_time|event_based|no_deadline|unknown>",
      "normalized_deadline": "<ISO date/time string or null>",
      "evidence": "<exact quote from raw communication or null>",
      "confidence": <float between 0.0 and 1.0>
    }
  ]
}
"""


def build_deadline_prompt(
    raw_content: str,
    actions: list[ExtractedAction],
    communication_timestamp: str | None = None,
    understanding: UnderstandingResult | None = None,
    responsibilities: list[ResponsibilityAssignment] | None = None,
    project_id: str | None = None,
    source_type: str | None = None,
) -> str:
    """
    Construct the user prompt for Module 5 deadline detection.

    The raw communication is the authoritative source.
    Actions from Module 3 define the exact set of items requiring deadline resolution.
    Timestamp, understanding (Module 2), and responsibilities (Module 4) provide context.
    """
    parts: list[str] = []

    parts.append("=== PRIMARY SOURCE OF TRUTH: RAW COMMUNICATION ===")
    if project_id:
        parts.append(f"Project ID: {project_id}")
    if source_type:
        parts.append(f"Source Type: {source_type}")
    if communication_timestamp:
        parts.append(f"Communication Timestamp: {communication_timestamp}")
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

    if responsibilities:
        parts.append("\n=== CONTEXTUAL ASSISTANCE (MODULE 4 RESPONSIBILITIES) ===")
        resp_map = {r.action_id: r for r in responsibilities}
        resp_summary = [
            f"- Action ID {aid}: Responsible Party = {r.responsible_party} ({r.responsibility_type})"
            for aid, r in resp_map.items()
            if r.responsible_party
        ]
        if resp_summary:
            parts.append("\n".join(resp_summary))

    parts.append("\n=== ACTIONS TO ASSIGN DEADLINE FOR (FROM MODULE 3) ===")
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
        "\nFor each action listed above, determine its deadline, deadline_type, normalized_deadline, "
        "evidence, and confidence. Map each strictly using its 'action_id'. "
        "Every action MUST have an assignment (use 'no_deadline' if none). "
        "Do NOT confuse meeting or discussion dates with action deadlines. "
        "Do NOT generate deadline_id. Do NOT include owner, decisions, or priorities. "
        "Output valid JSON only."
    )

    return "\n".join(parts)
