"""
ArchScale — Module 8: Project Memory / Searchable Memory
Core service: indexes upstream communication intelligence (M1-M7) into persistent,
searchable, traceable project memory and provides deterministic retrieval.
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Generator
from uuid import UUID, uuid4

from app.config import settings
from app.models.communication import CommunicationRecord
from app.models.decision import DecisionExtractionResult, ExtractedDecision
from app.models.memory import (
    DecisionItemData,
    MemoryItemType,
    MemorySearchRequest,
    MemorySearchResult,
    MemorySearchResultItem,
    ProjectDecisionsData,
    ProjectMemoryItem,
    ProjectMemoryOverview,
    ProjectTasksData,
    VALID_MEMORY_ITEM_TYPES,
)
from app.models.task import StructuredTask, StructuredTaskResult
from app.models.understanding import UnderstandingResult

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Stop words for deterministic natural query keyword extraction
# ---------------------------------------------------------------------------

STOP_WORDS: frozenset[str] = frozenset([
    "a", "about", "all", "an", "and", "are", "as", "at", "be", "been", "by",
    "did", "do", "does", "for", "from", "had", "happened", "has", "have",
    "he", "her", "his", "how", "i", "in", "is", "it", "its", "made", "me",
    "my", "need", "needed", "needs", "of", "on", "or", "our", "regarding",
    "she", "show", "that", "the", "their", "them", "there", "they", "this",
    "to", "was", "we", "were", "what", "when", "where", "which", "who",
    "whom", "will", "with", "would", "you", "your",
])


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class MemoryError(Exception):
    """Base exception for Module 8 memory operations."""


class MemoryValidationError(MemoryError):
    """Raised when memory input validation fails."""


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class MemoryService:
    """
    Persistent indexing and deterministic retrieval service for project memory.
    Consumes outputs from Modules 1-7 and exposes structured search without
    re-running upstream extraction or invoking an LLM.
    """

    def __init__(self, db_path: Path | str | None = None) -> None:
        if db_path is not None:
            self.db_path = Path(db_path)
        else:
            self.db_path = settings.storage_root_path / "memory.db"

        if str(self.db_path) != ":memory:":
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._init_db()

    @contextmanager
    def _get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Provide a contextual SQLite connection with row_factory enabled."""
        conn = sqlite3.connect(str(self.db_path), timeout=15.0)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_db(self) -> None:
        """Initialize the project_memory table and performance indexes."""
        with self._get_connection() as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS project_memory (
                    memory_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    item_type TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    communication_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    evidence TEXT,
                    metadata TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(project_id, item_type, source_id)
                );
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_mem_proj ON project_memory(project_id);"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_mem_type ON project_memory(item_type);"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_mem_source ON project_memory(source_id);"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_mem_comm ON project_memory(communication_id);"
            )

    # -----------------------------------------------------------------------
    # Idempotent Upsert Core
    # -----------------------------------------------------------------------

    def _save_memory_item(
        self,
        project_id: str,
        item_type: MemoryItemType,
        source_id: str | UUID,
        communication_id: str | UUID,
        title: str,
        content: str,
        evidence: str | None,
        metadata: dict[str, Any],
    ) -> ProjectMemoryItem:
        """
        Idempotently insert or update a ProjectMemoryItem.
        Guarantees that re-indexing the same (project_id, item_type, source_id)
        preserves the memory_id and created_at timestamp without duplicate rows.
        """
        clean_project_id = str(project_id).strip()
        clean_source_id = str(source_id).strip()
        clean_comm_id = str(communication_id).strip()
        clean_title = str(title).strip()
        clean_content = str(content).strip()
        clean_evidence = str(evidence).strip() if evidence else None

        if not clean_project_id:
            raise MemoryValidationError("project_id must not be blank.")
        if not clean_source_id:
            raise MemoryValidationError("source_id must not be blank.")
        if not clean_comm_id:
            raise MemoryValidationError("communication_id must not be blank.")
        if not clean_title:
            raise MemoryValidationError("title must not be blank.")
        if not clean_content:
            raise MemoryValidationError("content must not be blank.")
        if item_type not in VALID_MEMORY_ITEM_TYPES:
            raise MemoryValidationError(f"Invalid item_type: {item_type}")

        now_utc = datetime.now(timezone.utc).isoformat()
        metadata_json = json.dumps(metadata, ensure_ascii=False)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Check for existing entry to preserve memory_id and created_at
            cursor.execute(
                """
                SELECT memory_id, created_at FROM project_memory
                WHERE project_id = ? AND item_type = ? AND source_id = ?
                """,
                (clean_project_id, item_type, clean_source_id),
            )
            existing = cursor.fetchone()

            if existing:
                memory_id = existing["memory_id"]
                created_at_str = existing["created_at"]
                cursor.execute(
                    """
                    UPDATE project_memory
                    SET communication_id = ?,
                        title = ?,
                        content = ?,
                        evidence = ?,
                        metadata = ?,
                        updated_at = ?
                    WHERE memory_id = ?
                    """,
                    (
                        clean_comm_id,
                        clean_title,
                        clean_content,
                        clean_evidence,
                        metadata_json,
                        now_utc,
                        memory_id,
                    ),
                )
            else:
                memory_id = str(uuid4())
                created_at_str = now_utc
                cursor.execute(
                    """
                    INSERT INTO project_memory (
                        memory_id, project_id, item_type, source_id, communication_id,
                        title, content, evidence, metadata, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        memory_id,
                        clean_project_id,
                        item_type,
                        clean_source_id,
                        clean_comm_id,
                        clean_title,
                        clean_content,
                        clean_evidence,
                        metadata_json,
                        created_at_str,
                        now_utc,
                    ),
                )

        return ProjectMemoryItem(
            memory_id=UUID(memory_id),
            project_id=clean_project_id,
            item_type=item_type,
            source_id=clean_source_id,
            communication_id=clean_comm_id,
            title=clean_title,
            content=clean_content,
            evidence=clean_evidence,
            metadata=metadata,
            created_at=datetime.fromisoformat(created_at_str),
            updated_at=datetime.fromisoformat(now_utc),
        )

    # -----------------------------------------------------------------------
    # Entity Indexing Methods
    # -----------------------------------------------------------------------

    def index_communication(
        self,
        record: CommunicationRecord,
        understanding: UnderstandingResult | None = None,
    ) -> ProjectMemoryItem:
        """
        Index an ingested communication (Module 1) and its understanding (Module 2)
        into project memory.
        """
        title = (
            understanding.concise_summary
            if understanding and understanding.concise_summary
            else (
                record.raw_content[:80].strip() + "..."
                if len(record.raw_content) > 80
                else record.raw_content.strip()
            )
        )
        content = (
            understanding.detailed_summary
            if understanding and understanding.detailed_summary
            else record.raw_content.strip()
        )
        metadata: dict[str, Any] = {
            "source_type": getattr(record.source_type, "value", str(record.source_type)),
            "timestamp": record.timestamp.isoformat(),
            "topics": understanding.topics if understanding else [],
            "stakeholders": understanding.stakeholders if understanding else [],
            "communication_type": understanding.communication_type if understanding else "unknown",
            "storage_path": record.storage_path,
        }

        return self._save_memory_item(
            project_id=record.project_id,
            item_type="communication",
            source_id=str(record.communication_id),
            communication_id=str(record.communication_id),
            title=title,
            content=content,
            evidence=record.raw_content[:300],
            metadata=metadata,
        )

    def index_task(self, task: StructuredTask) -> ProjectMemoryItem:
        """
        Index a structured task (Module 7) into project memory with full provenance.
        """
        metadata: dict[str, Any] = {
            "task_id": str(task.task_id),
            "action_id": str(task.action_id),
            "responsible_party": task.responsible_party,
            "responsibility_type": task.responsibility_type,
            "deadline": task.deadline,
            "deadline_type": task.deadline_type,
            "normalized_deadline": task.normalized_deadline,
            "status": task.status,
            "priority": task.priority,
            "decision_context": task.decision_context,
            "task_created_at": task.created_at.isoformat(),
        }

        return self._save_memory_item(
            project_id=task.project_id,
            item_type="task",
            source_id=str(task.task_id),
            communication_id=str(task.communication_id),
            title=task.title,
            content=task.description,
            evidence=task.evidence,
            metadata=metadata,
        )

    def index_decision(
        self,
        decision: ExtractedDecision,
        project_id: str,
        communication_id: str | UUID,
    ) -> ProjectMemoryItem:
        """
        Index an extracted decision or approval (Module 6) into project memory.
        """
        item_type: MemoryItemType = "approval" if decision.item_type == "approval" else "decision"
        title = (
            f"{decision.subject}: {decision.description}"
            if decision.subject
            else decision.description
        )
        metadata: dict[str, Any] = {
            "decision_id": str(decision.decision_id),
            "item_type": decision.item_type,
            "subject": decision.subject,
            "status": decision.status,
            "confidence": decision.confidence,
        }

        return self._save_memory_item(
            project_id=project_id,
            item_type=item_type,
            source_id=str(decision.decision_id),
            communication_id=str(communication_id),
            title=title,
            content=decision.description,
            evidence=decision.evidence,
            metadata=metadata,
        )

    def index_project(
        self,
        project_id: str,
        communications: list[CommunicationRecord] | None = None,
        understandings: list[UnderstandingResult] | None = None,
        decisions: list[ExtractedDecision] | DecisionExtractionResult | None = None,
        tasks: list[StructuredTask] | StructuredTaskResult | None = None,
        communication_id: str | None = None,
    ) -> list[ProjectMemoryItem]:
        """
        Index pre-extracted project objects from Modules 1, 2, 6, and 7.
        Does NOT execute upstream extraction. Consumes already-produced models only.
        """
        clean_project_id = str(project_id).strip()
        if not clean_project_id:
            raise MemoryValidationError("project_id must not be blank.")

        indexed_items: list[ProjectMemoryItem] = []

        # Index communications paired with understandings if matching communication_id
        if communications:
            understanding_by_comm: dict[str, UnderstandingResult] = {}
            if understandings:
                for u in understandings:
                    understanding_by_comm[str(u.communication_id)] = u

            for comm in communications:
                if comm.project_id != clean_project_id:
                    continue
                und = understanding_by_comm.get(str(comm.communication_id))
                item = self.index_communication(comm, und)
                indexed_items.append(item)

        # Index decisions
        if decisions is not None:
            dec_list: list[ExtractedDecision] = (
                decisions.decisions if isinstance(decisions, DecisionExtractionResult) else decisions
            )
            comm_id_fallback = communication_id or "unknown"
            for dec in dec_list:
                item = self.index_decision(
                    decision=dec,
                    project_id=clean_project_id,
                    communication_id=comm_id_fallback,
                )
                indexed_items.append(item)

        # Index tasks
        if tasks is not None:
            task_list: list[StructuredTask] = (
                tasks.tasks if isinstance(tasks, StructuredTaskResult) else tasks
            )
            for t in task_list:
                if t.project_id != clean_project_id:
                    continue
                item = self.index_task(t)
                indexed_items.append(item)

        logger.info(
            "Project %s: indexed %d memory items.",
            clean_project_id,
            len(indexed_items),
        )
        return indexed_items

    # -----------------------------------------------------------------------
    # Deterministic Search & Ranking (Embedding-Free)
    # -----------------------------------------------------------------------

    def search(self, request: MemorySearchRequest) -> MemorySearchResult:
        """
        Search across indexed project memory with deterministic keyword ranking
        and strict project isolation.
        """
        project_id = request.project_id.strip()
        if not project_id:
            raise MemoryValidationError("project_id must not be blank.")

        # 1. Fetch candidate records strictly for this project
        query_sql = "SELECT * FROM project_memory WHERE project_id = ?"
        params: list[Any] = [project_id]

        if request.item_type:
            query_sql += " AND item_type = ?"
            params.append(request.item_type)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query_sql, params)
            rows = cursor.fetchall()

        if not rows:
            return MemorySearchResult(
                project_id=project_id,
                query=request.query,
                results=[],
                result_count=0,
                retrieval_mode="keyword",
            )

        # 2. Prepare query tokens and exact phrase
        raw_query = request.query.strip().lower()
        query_tokens = [w for w in re.findall(r"[a-zA-Z0-9_\-]+", raw_query) if w]
        content_tokens = [w for w in query_tokens if w not in STOP_WORDS]
        tokens_to_match = content_tokens if content_tokens else query_tokens

        # Check for query intent keywords
        has_task_intent = any(w in raw_query for w in ("task", "tasks", "action", "assigned"))
        has_decision_intent = any(
            w in raw_query for w in ("decision", "decisions", "decided", "approval", "approvals", "approve", "approved")
        )

        scored_items: list[MemorySearchResultItem] = []

        for row in rows:
            meta: dict[str, Any] = json.loads(row["metadata"])

            # Filter by responsible_party (task owner)
            if request.responsible_party:
                owner = str(meta.get("responsible_party") or "").lower()
                if request.responsible_party.lower() not in owner:
                    continue

            # Filter by status
            if request.status:
                status_val = str(meta.get("status") or "").lower()
                if request.status.lower() != status_val:
                    continue

            # Filter by deadline
            if request.deadline:
                dl = str(meta.get("deadline") or "").lower()
                norm_dl = str(meta.get("normalized_deadline") or "").lower()
                req_dl = request.deadline.lower()
                if req_dl not in dl and req_dl not in norm_dl:
                    continue

            # If no query string was provided, assign a baseline score
            if not raw_query:
                scored_items.append(
                    MemorySearchResultItem(
                        memory_id=row["memory_id"],
                        project_id=row["project_id"],
                        item_type=row["item_type"],
                        source_id=row["source_id"],
                        communication_id=row["communication_id"],
                        title=row["title"],
                        content=row["content"],
                        evidence=row["evidence"],
                        metadata=meta,
                        score=1.0,
                        retrieval_mode="keyword",
                    )
                )
                continue

            # 3. Deterministic scoring
            title_lower = row["title"].lower()
            content_lower = row["content"].lower()
            evidence_lower = (row["evidence"] or "").lower()
            meta_str = " ".join(str(v) for v in meta.values()).lower()

            score = 0.0

            # Exact phrase matching (+10 for title with density bonus, +8 for content/evidence)
            if len(raw_query) > 2:
                if raw_query in title_lower:
                    density = len(raw_query) / max(len(title_lower), 1)
                    score += 10.0 + round(5.0 * density, 2)
                if raw_query in content_lower:
                    score += 8.0
                if raw_query in evidence_lower:
                    score += 8.0

            # Query token matching (+6 in title, +4 in content, +3 in evidence, +2 in metadata)
            for token in tokens_to_match:
                token_matched = False
                if token in title_lower:
                    score += 6.0
                    token_matched = True
                if token in content_lower:
                    score += 4.0
                    token_matched = True
                if token in evidence_lower:
                    score += 3.0
                    token_matched = True
                if token in meta_str:
                    score += 2.0
                    token_matched = True

                # Light stemming / prefix matching (e.g. approve -> approved, drawing -> drawings)
                if not token_matched and len(token) >= 4:
                    stem = token[:4]
                    if stem in title_lower:
                        score += 3.0
                    elif stem in content_lower:
                        score += 2.0
                    elif stem in evidence_lower:
                        score += 1.5

            # Intent-based boost
            if has_task_intent and row["item_type"] == "task":
                score += 3.0
            if has_decision_intent and row["item_type"] in ("decision", "approval"):
                score += 3.0

            # Only retain items with positive relevance score
            if score > 0.0:
                scored_items.append(
                    MemorySearchResultItem(
                        memory_id=row["memory_id"],
                        project_id=row["project_id"],
                        item_type=row["item_type"],
                        source_id=row["source_id"],
                        communication_id=row["communication_id"],
                        title=row["title"],
                        content=row["content"],
                        evidence=row["evidence"],
                        metadata=meta,
                        score=round(score, 2),
                        retrieval_mode="keyword",
                    )
                )

        # 4. Deterministic sorting: highest score first, tie-break by title and memory_id
        scored_items.sort(key=lambda item: (-item.score, item.title, str(item.memory_id)))

        results = scored_items[: request.limit]
        return MemorySearchResult(
            project_id=project_id,
            query=request.query,
            results=results,
            result_count=len(results),
            retrieval_mode="keyword",
        )

    # -----------------------------------------------------------------------
    # Retrieval Views
    # -----------------------------------------------------------------------

    def get_project_memory(self, project_id: str) -> ProjectMemoryOverview:
        """
        Return statistical summary counts of indexed memory for a project.
        """
        clean_project_id = str(project_id).strip()
        if not clean_project_id:
            raise MemoryValidationError("project_id must not be blank.")

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT item_type, COUNT(*) as count
                FROM project_memory
                WHERE project_id = ?
                GROUP BY item_type
                """,
                (clean_project_id,),
            )
            rows = cursor.fetchall()

        counts: dict[str, int] = {r["item_type"]: r["count"] for r in rows}
        total = sum(counts.values())

        return ProjectMemoryOverview(
            project_id=clean_project_id,
            communications=counts.get("communication", 0),
            tasks=counts.get("task", 0),
            decisions=counts.get("decision", 0),
            approvals=counts.get("approval", 0),
            memory_items=total,
        )

    def get_project_tasks(
        self,
        project_id: str,
        status: str | None = None,
        responsible_party: str | None = None,
        deadline: str | None = None,
    ) -> ProjectTasksData:
        """
        Retrieve existing indexed M7 tasks without recreating or re-interpreting them.
        """
        clean_project_id = str(project_id).strip()
        if not clean_project_id:
            raise MemoryValidationError("project_id must not be blank.")

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM project_memory
                WHERE project_id = ? AND item_type = 'task'
                ORDER BY created_at ASC
                """,
                (clean_project_id,),
            )
            rows = cursor.fetchall()

        tasks: list[StructuredTask] = []
        for r in rows:
            meta = json.loads(r["metadata"])

            if status and meta.get("status", "").lower() != status.lower():
                continue
            if responsible_party:
                party = str(meta.get("responsible_party") or "").lower()
                if responsible_party.lower() not in party:
                    continue
            if deadline:
                dl = str(meta.get("deadline") or "").lower()
                norm_dl = str(meta.get("normalized_deadline") or "").lower()
                if deadline.lower() not in dl and deadline.lower() not in norm_dl:
                    continue

            task = StructuredTask(
                task_id=UUID(r["source_id"]) if _is_valid_uuid(r["source_id"]) else uuid4(),
                project_id=r["project_id"],
                communication_id=r["communication_id"],
                action_id=meta.get("action_id", r["source_id"]),
                title=r["title"],
                description=r["content"],
                responsible_party=meta.get("responsible_party"),
                responsibility_type=meta.get("responsibility_type"),
                deadline=meta.get("deadline"),
                deadline_type=meta.get("deadline_type", "no_deadline"),
                normalized_deadline=meta.get("normalized_deadline"),
                status=meta.get("status", "pending"),
                priority=meta.get("priority", "unspecified"),
                evidence=r["evidence"] or r["content"],
                decision_context=meta.get("decision_context", []),
                created_at=datetime.fromisoformat(meta.get("task_created_at", r["created_at"])),
            )
            tasks.append(task)

        return ProjectTasksData(
            project_id=clean_project_id,
            tasks=tasks,
            task_count=len(tasks),
        )

    def get_project_decisions(self, project_id: str) -> ProjectDecisionsData:
        """
        Retrieve existing indexed M6 decisions/approvals without re-interpreting them.
        """
        clean_project_id = str(project_id).strip()
        if not clean_project_id:
            raise MemoryValidationError("project_id must not be blank.")

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM project_memory
                WHERE project_id = ? AND item_type IN ('decision', 'approval')
                ORDER BY created_at ASC
                """,
                (clean_project_id,),
            )
            rows = cursor.fetchall()

        decisions: list[DecisionItemData] = []
        for r in rows:
            meta = json.loads(r["metadata"])
            decisions.append(
                DecisionItemData(
                    decision_id=r["source_id"],
                    item_type=meta.get("item_type", r["item_type"]),
                    description=r["content"],
                    subject=meta.get("subject"),
                    status=meta.get("status", "decided"),
                    evidence=r["evidence"] or "",
                    communication_id=r["communication_id"],
                )
            )

        return ProjectDecisionsData(
            project_id=clean_project_id,
            decisions=decisions,
            decision_count=len(decisions),
        )


def _is_valid_uuid(val: str) -> bool:
    try:
        UUID(val)
        return True
    except (ValueError, AttributeError, TypeError):
        return False
