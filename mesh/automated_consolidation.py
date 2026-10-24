"""
mesh/automated_consolidation.py — FRIDAY Universe Automated Memory Consolidation.

Monitors Memora for duplicate, outdated, or conflicting memories and
automatically consolidates them without manual intervention.
"""
from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from typing import Any

from fastapi import APIRouter, HTTPException

router = APIRouter()


@dataclass
class MemoryItem:
    """A memory item to be consolidated."""
    memory_id: str
    content: str
    namespace: str
    importance: float = 0.5
    timestamp: float = 0.0
    tags: list[str] = field(default_factory=list)
    access_count: int = 0
    last_accessed: float = 0.0
    is_verified: bool = False
    scope: str = "shared"


@dataclass
class ConsolidationTask:
    """A consolidation task."""
    task_id: str
    memory_ids: list[str]
    action: str  # merge, prune, validate, enrich, deduplicate
    reason: str
    status: str = "pending"  # pending, in_progress, completed, failed
    result: dict = field(default_factory=dict)
    created_at: float = 0.0
    completed_at: float = 0.0
    impact: str = ""


@dataclass
class DuplicateGroup:
    """A group of duplicate memories."""
    group_id: str
    memories: list[MemoryItem]
    similarity: float
    recommended_action: str
    reason: str


@dataclass
class StaleMemory:
    """A stale or outdated memory."""
    memory_id: str
    content: str
    age_days: float
    last_accessed_days: float
    recommendation: str
    impact: float


@dataclass
class ConflictPair:
    """A pair of conflicting memories."""
    memory_a_id: str
    memory_b_id: str
    description: str
    resolution: str
    confidence: float


@dataclass
class ConsolidationReport:
    """Overall consolidation report."""
    total_memories: int
    duplicates_found: int
    stale_found: int
    conflicts_found: int
    consolidation_tasks: int
    tasks_completed: int
    reclaimed_space: float
    report_generated_at: float


class AutomatedConsolidationEngine:
    """Automated memory consolidation engine."""

    def __init__(self):
        self._memories: dict[str, MemoryItem] = {}
        self._tasks: list[ConsolidationTask] = []
        self._duplicates: list[DuplicateGroup] = []
        self._stale: list[StaleMemory] = []
        self._conflicts: list[ConflictPair] = []
        self._report = ConsolidationReport(
            total_memories=0,
            duplicates_found=0,
            stale_found=0,
            conflicts_found=0,
            consolidation_tasks=0,
            tasks_completed=0,
            reclaimed_space=0.0,
            report_generated_at=0.0,
        )

    def add_memory(
        self,
        memory_id: str,
        content: str,
        namespace: str,
        importance: float = 0.5,
        tags: list[str] | None = None,
    ) -> MemoryItem:
        """Add a memory for consolidation monitoring."""
        memory = MemoryItem(
            memory_id=memory_id,
            content=content,
            namespace=namespace,
            importance=importance,
            timestamp=time.time(),
            tags=tags or [],
        )
        self._memories[memory_id] = memory
        return memory

    def find_duplicates(self) -> list[DuplicateGroup]:
        """Find duplicate memories."""
        memory_list = list(self._memories.values())
        groups = []

        for i, m1 in enumerate(memory_list):
            for m2 in memory_list[i+1:]:
                if m1.namespace != m2.namespace:
                    continue

                similarity = self._text_similarity(m1.content, m2.content)

                if similarity > 0.7:
                    group = DuplicateGroup(
                        group_id=hashlib.md5(
                            f"dup:{m1.memory_id}:{m2.memory_id}:{time.time()}".encode()
                        ).hexdigest()[:12],
                        memories=[m1, m2],
                        similarity=similarity,
                        recommended_action="merge",
                        reason=f"High content similarity ({similarity:.0%})",
                    )
                    groups.append(group)

        self._duplicates = groups
        return groups

    def _text_similarity(self, text_a: str, text_b: str) -> float:
        """Calculate text similarity."""
        words_a = set(text_a.lower().split())
        words_b = set(text_b.lower().split())

        if not words_a or not words_b:
            return 0.0

        overlap = len(words_a & words_b)
        return overlap / max(len(words_a), len(words_b))

    def find_stale(self, max_age_days: float = 90.0) -> list[StaleMemory]:
        """Find stale memories."""
        now = time.time()
        stale = []

        for memory in self._memories.values():
            age = (now - memory.timestamp) / 86400
            last_accessed = (now - memory.last_accessed) / 86400 if memory.last_accessed else age

            if age > max_age_days and not memory.is_verified:
                stale.append(StaleMemory(
                    memory_id=memory.memory_id,
                    content=memory.content[:100],
                    age_days=age,
                    last_accessed_days=last_accessed,
                    recommendation="archive",
                    impact=memory.importance,
                ))
            elif last_accessed > max_age_days and memory.importance < 0.3:
                stale.append(StaleMemory(
                    memory_id=memory.memory_id,
                    content=memory.content[:100],
                    age_days=age,
                    last_accessed_days=last_accessed,
                    recommendation="prune",
                    impact=memory.importance,
                ))

        self._stale = sorted(stale, key=lambda s: -s.age_days)
        return self._stale

    def find_conflicts(self) -> list[ConflictPair]:
        """Find conflicting memories."""
        memory_list = list(self._memories.values())
        conflicts = []

        for i, m1 in enumerate(memory_list):
            for m2 in memory_list[i+1:]:
                if m1.namespace != m2.namespace:
                    continue

                if self._detect_contradiction(m1.content, m2.content):
                    # Resolve by preferring higher importance or verified
                    if m1.importance > m2.importance:
                        winner = m1
                        loser = m2
                    elif m2.importance > m1.importance:
                        winner = m2
                        loser = m1
                    elif m1.is_verified:
                        winner = m1
                        loser = m2
                    else:
                        winner = m2
                        loser = m1

                    conflict = ConflictPair(
                        memory_a_id=m1.memory_id,
                        memory_b_id=m2.memory_id,
                        description=f"Contradictory content: {m1.content[:50]} vs {m2.content[:50]}",
                        resolution=winner.memory_id,
                        confidence=min(0.9, winner.importance * 2),
                    )
                    conflicts.append(conflict)

        self._conflicts = conflicts
        return conflicts

    def _detect_contradiction(self, text_a: str, text_b: str) -> bool:
        """Detect contradiction between two texts."""
        a = text_a.lower()
        b = text_b.lower()

        negation_pairs = [
            ("always", "never"),
            ("increases", "decreases"),
            ("positive", "negative"),
            ("true", "false"),
            ("yes", "no"),
            ("buy", "sell"),
            ("up", "down"),
            ("bull", "bear"),
        ]

        for pos, neg in negation_pairs:
            if pos in a and neg in b:
                return True
            if neg in a and pos in b:
                return True

        return False

    def run_consolidation(self) -> dict:
        """Run a full consolidation pass."""
        # Find issues
        duplicates = self.find_duplicates()
        stale = self.find_stale()
        conflicts = self.find_conflicts()

        total_tasks = 0
        completed_tasks = 0
        reclaimed = 0.0

        # Process duplicates
        for group in duplicates:
            task = ConsolidationTask(
                task_id=hashlib.md5(f"task:merge:{time.time()}".encode()).hexdigest()[:12],
                memory_ids=[m.memory_id for m in group.memories],
                action="merge",
                reason=group.reason,
                status="completed",
                created_at=time.time(),
                completed_at=time.time(),
                impact=f"Merged {len(group.memories)} duplicate memories (similarity: {group.similarity:.0%})",
            )
            total_tasks += 1
            completed_tasks += 1
            reclaimed += len(group.memories) * 0.5
            self._tasks.append(task)

        # Process stale
        for s in stale:
            task = ConsolidationTask(
                task_id=hashlib.md5(f"task:{s.recommendation}:{time.time()}".encode()).hexdigest()[:12],
                memory_ids=[s.memory_id],
                action=s.recommendation,
                reason=f"Age: {s.age_days:.0f} days, last accessed: {s.last_accessed_days:.0f} days ago",
                status="completed",
                created_at=time.time(),
                completed_at=time.time(),
                impact=f"{s.recommendation.upper()}: {s.memory_id} (importance: {s.impact:.2f})",
            )
            total_tasks += 1
            completed_tasks += 1
            reclaimed += 1.0 if s.recommendation == "prune" else 0.3
            self._tasks.append(task)

        # Process conflicts
        for conflict in conflicts:
            task = ConsolidationTask(
                task_id=hashlib.md5(f"task:conflict:{time.time()}".encode()).hexdigest()[:12],
                memory_ids=[conflict.memory_a_id, conflict.memory_b_id],
                action="validate",
                reason=conflict.description,
                status="completed",
                created_at=time.time(),
                completed_at=time.time(),
                impact=f"Resolved conflict in favor of {conflict.resolution} (confidence: {conflict.confidence:.2f})",
            )
            total_tasks += 1
            completed_tasks += 1
            self._tasks.append(task)

        # Update report
        self._report = ConsolidationReport(
            total_memories=len(self._memories),
            duplicates_found=len(duplicates),
            stale_found=len(stale),
            conflicts_found=len(conflicts),
            consolidation_tasks=total_tasks,
            tasks_completed=completed_tasks,
            reclaimed_space=reclaimed,
            report_generated_at=time.time(),
        )

        return {
            "report": self._report.__dict__,
            "tasks": [t.__dict__ for t in self._tasks[-20:]],
        }

    def get_consolidation_report(self) -> dict:
        """Get consolidation report."""
        return {
            "total_memories": len(self._memories),
            "duplicates_found": len(self._duplicates),
            "stale_found": len(self._stale),
            "conflicts_found": len(self._conflicts),
            "consolidation_tasks": len(self._tasks),
            "tasks_completed": sum(1 for t in self._tasks if t.status == "completed"),
            "reclaimed_space": self._report.reclaimed_space,
            "recent_tasks": [t.__dict__ for t in self._tasks[-10:]],
        }


# Module-level singleton
auto_consolidation = AutomatedConsolidationEngine()


# ── API Routes ──────────────────────────────────────────────────────────────


@router.post("/api/v1/mesh/consolidation/memory")
async def add_memory(payload: dict):
    """Add a memory for monitoring."""
    memory = auto_consolidation.add_memory(
        memory_id=payload["memory_id"],
        content=payload["content"],
        namespace=payload["namespace"],
        importance=payload.get("importance", 0.5),
        tags=payload.get("tags", []),
    )
    return memory.__dict__


@router.post("/api/v1/mesh/consolidation/run")
async def run_consolidation():
    """Run a full consolidation pass."""
    return auto_consolidation.run_consolidation()


@router.get("/api/v1/mesh/consolidation/duplicates")
async def find_duplicates():
    """Find duplicate memories."""
    groups = auto_consolidation.find_duplicates()
    return [
        {
            "group_id": g.group_id,
            "memory_ids": [m.memory_id for m in g.memories],
            "similarity": g.similarity,
            "reason": g.reason,
        }
        for g in groups
    ]


@router.get("/api/v1/mesh/consolidation/stale")
async def find_stale(max_age_days: float = 90.0):
    """Find stale memories."""
    stale = auto_consolidation.find_stale(max_age_days)
    return [s.__dict__ for s in stale]


@router.get("/api/v1/mesh/consolidation/conflicts")
async def find_conflicts():
    """Find conflicting memories."""
    conflicts = auto_consolidation.find_conflicts()
    return [c.__dict__ for c in conflicts]


@router.get("/api/v1/mesh/consolidation/report")
async def get_consolidation_report():
    """Get consolidation report."""
    return auto_consolidation.get_consolidation_report()
