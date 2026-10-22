"""Universal Memory Fabric for FRIDAY Universe Ecosystem.

Phase 2: Universal Memory Fabric (Memora Integration).
Provides 3-tiered memory scoping:
- Agent (private memory per agent)
- Group (shared memory for agent sub-teams)
- Universal (global ecosystem memory shared across all 9 agents)

Includes:
- Auto-ingestion of tool executions and error outcomes
- Nightly Lesson Distiller converting failures into procedural rules (lessons_applied ledger)
- Dual-mode: Cloud-First (Memora on Render) with fail-safe local persistence
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("memory_fabric")


class MemoryScope(str, Enum):
    AGENT = "agent"          # Private to individual agent
    GROUP = "group"          # Shared within an agent cluster (e.g. trading, engineering)
    UNIVERSAL = "universal"  # Ecosystem-wide knowledge fabric


# Predefined functional agent groups for sub-team collaboration
AGENT_GROUPS: Dict[str, List[str]] = {
    "orchestration": ["FRIDAY", "INFERENCE"],
    "engineering": ["FORGE", "SENTINEL"],
    "trading": ["STRATEX", "FUTURIS"],
    "research": ["INTELX", "CORTEX"],
    "cognition": ["MEMORA", "FRIDAY", "INFERENCE"],
}


@dataclass
class MemoryEntry:
    id: str = field(default_factory=lambda: f"mem_{uuid.uuid4().hex[:12]}")
    scope: MemoryScope = MemoryScope.AGENT
    owner_agent: str = ""
    group_name: Optional[str] = None
    namespace: str = ""
    memory_type: str = "episodic"  # episodic, semantic, procedural, experience
    content_text: str = ""
    source: str = "agent"
    confidence: float = 1.0
    importance: float = 0.7
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=lambda: time.time())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemoryEntry":
        scope_val = data.get("scope", "agent")
        if isinstance(scope_val, str):
            scope = MemoryScope(scope_val.lower())
        else:
            scope = scope_val
        return cls(
            id=data.get("id", f"mem_{uuid.uuid4().hex[:12]}"),
            scope=scope,
            owner_agent=data.get("owner_agent", "").upper(),
            group_name=data.get("group_name"),
            namespace=data.get("namespace", ""),
            memory_type=data.get("memory_type", "episodic"),
            content_text=data.get("content_text", ""),
            source=data.get("source", "agent"),
            confidence=float(data.get("confidence", 1.0)),
            importance=float(data.get("importance", 0.7)),
            metadata=data.get("metadata", {}),
            created_at=float(data.get("created_at", time.time())),
        )


@dataclass
class DistilledLesson:
    id: str = field(default_factory=lambda: f"lsn_{uuid.uuid4().hex[:8]}")
    agent_name: str = ""
    domain: str = "operational"
    trigger_error: str = ""
    rule: str = ""
    context: str = ""
    scope: MemoryScope = MemoryScope.UNIVERSAL
    confidence: float = 0.95
    importance: float = 0.95
    applied_count: int = 0
    created_at: float = field(default_factory=lambda: time.time())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class UniversalMemoryFabric:
    """Universal Memory Fabric connecting all 9 agents to Memora.
    Routes to Render Cloud (0% laptop CPU strain) with seamless local fallback.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        local_db_path: Optional[str] = None,
        timeout: float = 5.0,
    ):
        self.base_url = (base_url or os.getenv("MEMORA_URL", "http://memora:8000")).rstrip("/")
        self.api_key = api_key or os.getenv("MEMORA_API_KEY", "memora_api")
        self.timeout = timeout

        # Local storage setup
        if local_db_path:
            self.local_db_path = local_db_path
        else:
            default_dir = Path(__file__).resolve().parent.parent / "reports_and_data" / "memora"
            default_dir.mkdir(parents=True, exist_ok=True)
            self.local_db_path = str(default_dir / "fabric_local.db")

        self._in_memory_records: List[MemoryEntry] = []
        self._init_local_db()

    def _init_local_db(self) -> None:
        try:
            with sqlite3.connect(self.local_db_path, timeout=5.0) as conn:
                c = conn.cursor()
                c.execute("""
                    CREATE TABLE IF NOT EXISTS fabric_memories (
                        id TEXT PRIMARY KEY,
                        scope TEXT NOT NULL,
                        owner_agent TEXT NOT NULL,
                        group_name TEXT,
                        namespace TEXT NOT NULL,
                        memory_type TEXT NOT NULL,
                        content_text TEXT NOT NULL,
                        source TEXT,
                        confidence REAL,
                        importance REAL,
                        metadata_json TEXT,
                        created_at REAL
                    )
                """)
                c.execute("""
                    CREATE TABLE IF NOT EXISTS lessons_applied (
                        id TEXT PRIMARY KEY,
                        agent_name TEXT NOT NULL,
                        domain TEXT NOT NULL,
                        trigger_error TEXT,
                        rule TEXT NOT NULL,
                        context TEXT,
                        scope TEXT NOT NULL,
                        confidence REAL,
                        importance REAL,
                        applied_count INTEGER DEFAULT 0,
                        created_at REAL
                    )
                """)
                conn.commit()
        except Exception as e:
            logger.debug(f"Local fabric DB init notice: {e}")

    def build_namespace(
        self,
        agent_name: str,
        scope: MemoryScope = MemoryScope.AGENT,
        group_name: Optional[str] = None,
    ) -> str:
        agent = agent_name.upper().strip()
        if scope == MemoryScope.UNIVERSAL:
            return "memora://universe/global"
        elif scope == MemoryScope.GROUP:
            grp = group_name or self.get_agent_primary_group(agent)
            return f"memora://groups/{grp.lower()}"
        else:
            return f"memora://{agent.lower()}/private"

    def get_agent_primary_group(self, agent_name: str) -> str:
        agent = agent_name.upper()
        for group, members in AGENT_GROUPS.items():
            if agent in members:
                return group
        return "general"

    def record(
        self,
        owner_agent: str,
        content_text: str,
        scope: MemoryScope = MemoryScope.AGENT,
        group_name: Optional[str] = None,
        memory_type: str = "episodic",
        importance: float = 0.7,
        confidence: float = 1.0,
        source: str = "agent_operation",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> MemoryEntry:
        """Record an entry into the fabric across the designated scope."""
        owner = owner_agent.upper().strip()
        namespace = self.build_namespace(owner, scope, group_name)

        entry = MemoryEntry(
            id=f"mem_{uuid.uuid4().hex[:12]}",
            scope=scope,
            owner_agent=owner,
            group_name=group_name or (self.get_agent_primary_group(owner) if scope == MemoryScope.GROUP else None),
            namespace=namespace,
            memory_type=memory_type,
            content_text=content_text,
            source=source,
            confidence=confidence,
            importance=importance,
            metadata=metadata or {},
            created_at=time.time(),
        )

        # Store in fast memory cache
        self._in_memory_records.append(entry)

        # Persist locally in SQLite
        self._save_local_record(entry)

        # Asynchronously dispatch to Cloud Memora
        self._dispatch_to_cloud(entry)

        return entry

    def _save_local_record(self, entry: MemoryEntry) -> None:
        try:
            with sqlite3.connect(self.local_db_path, timeout=5.0) as conn:
                c = conn.cursor()
                c.execute("""
                    INSERT OR REPLACE INTO fabric_memories
                    (id, scope, owner_agent, group_name, namespace, memory_type, content_text, source, confidence, importance, metadata_json, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    entry.id,
                    entry.scope.value,
                    entry.owner_agent,
                    entry.group_name,
                    entry.namespace,
                    entry.memory_type,
                    entry.content_text,
                    entry.source,
                    entry.confidence,
                    entry.importance,
                    json.dumps(entry.metadata),
                    entry.created_at,
                ))
                conn.commit()
        except Exception as e:
            logger.debug(f"Local record save failed: {e}")

    def _dispatch_to_cloud(self, entry: MemoryEntry) -> bool:
        url = f"{self.base_url}/v1/memories"
        payload = {
            "id": entry.id,
            "content_text": entry.content_text,
            "memory_type": entry.memory_type,
            "namespace": entry.namespace,
            "scope": entry.scope.value,
            "owner": entry.owner_agent,
            "source": entry.source,
            "confidence": entry.confidence,
            "importance": entry.importance,
            "metadata": entry.metadata,
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "X-Agent-Name": entry.owner_agent.lower(),
        }
        try:
            req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return resp.status in (200, 201)
        except Exception:
            # Graceful degrade to local storage
            return False

    def recall(
        self,
        query: str,
        agent_name: str,
        scope: Optional[MemoryScope] = None,
        limit: int = 5,
    ) -> List[MemoryEntry]:
        """Recall memories accessible to the agent across specified or all valid scopes."""
        agent = agent_name.upper().strip()
        tokens = [t.lower() for t in query.split() if len(t) > 2]

        results: List[tuple[float, MemoryEntry]] = []

        # Query candidates from in-memory and local SQLite
        candidates = list(self._in_memory_records)

        # Also pull from local DB
        try:
            with sqlite3.connect(self.local_db_path, timeout=5.0) as conn:
                c = conn.cursor()
                c.execute("SELECT id, scope, owner_agent, group_name, namespace, memory_type, content_text, source, confidence, importance, metadata_json, created_at FROM fabric_memories")
                for row in c.fetchall():
                    entry = MemoryEntry(
                        id=row[0],
                        scope=MemoryScope(row[1]),
                        owner_agent=row[2],
                        group_name=row[3],
                        namespace=row[4],
                        memory_type=row[5],
                        content_text=row[6],
                        source=row[7],
                        confidence=row[8],
                        importance=row[9],
                        metadata=json.loads(row[10]) if row[10] else {},
                        created_at=row[11],
                    )
                    if not any(c.id == entry.id for c in candidates):
                        candidates.append(entry)
        except Exception:
            pass

        agent_group = self.get_agent_primary_group(agent)

        for item in candidates:
            # Scope filtering
            if scope and item.scope != scope:
                continue

            # Access permission check:
            # 1. UNIVERSAL is accessible to all
            # 2. GROUP is accessible if agent is in the group
            # 3. AGENT is accessible only to the owner
            if item.scope == MemoryScope.UNIVERSAL:
                allowed = True
            elif item.scope == MemoryScope.GROUP:
                allowed = (item.group_name == agent_group) or (item.owner_agent == agent)
            else:
                allowed = (item.owner_agent == agent)

            if not allowed:
                continue

            # Scoring
            content_lower = item.content_text.lower()
            if tokens:
                matches = sum(1 for t in tokens if t in content_lower)
                if matches == 0:
                    continue
                score = (matches / len(tokens)) * item.importance
            else:
                score = item.importance

            results.append((score, item))

        results.sort(key=lambda x: (x[0], x[1].importance, x[1].created_at), reverse=True)
        return [r[1] for r in results[:limit]]

    def record_auto_ingested_event(
        self,
        agent_name: str,
        action: str,
        status: str,
        payload_summary: str,
        error_msg: Optional[str] = None,
    ) -> MemoryEntry:
        """Auto-ingestion hook for agent tool/task executions."""
        scope = MemoryScope.UNIVERSAL if status.lower() in ("error", "failed") else MemoryScope.AGENT
        content = f"[{agent_name.upper()}] Action: {action} | Status: {status.upper()} | Summary: {payload_summary}"
        if error_msg:
            content += f" | Error: {error_msg}"

        return self.record(
            owner_agent=agent_name,
            content_text=content,
            scope=scope,
            memory_type="episodic",
            importance=0.85 if error_msg else 0.60,
            metadata={"action": action, "status": status, "has_error": bool(error_msg)},
        )


class NightlyLessonDistiller:
    """Nightly Lesson Distiller.
    Scans episodic execution logs and failure events across all 9 agents,
    distilling actionable procedural rules into the `lessons_applied` ledger.
    """

    def __init__(self, fabric: UniversalMemoryFabric):
        self.fabric = fabric

    @staticmethod
    def extract_distilled_rule(agent_name: str, task_name: str, error_log: str, domain: str = "operational") -> str:
        """Extract a deterministic procedural remediation rule from an error trace."""
        err_lower = (error_log or "").lower()

        if "permission" in err_lower or "access denied" in err_lower:
            return f"Verify OS security elevation and API token credentials before initiating '{task_name}'."
        elif "not found" in err_lower or "no such file" in err_lower:
            return f"Validate absolute path existence and verify target asset is staged prior to executing '{task_name}'."
        elif "timeout" in err_lower or "timed out" in err_lower:
            return f"Configure 30s timeout budget with exponential backoff retries when dispatching '{task_name}'."
        elif "connection refused" in err_lower or "unreachable" in err_lower:
            return f"Perform pre-flight health probe verification before connecting to endpoint in '{task_name}'."
        elif "rate limit" in err_lower or "429" in err_lower:
            return f"Engage token bucket rate limiter and fall back to secondary key pool in '{task_name}'."
        elif "drawdown" in err_lower or "volatil" in err_lower or "liquidation" in err_lower:
            return f"Enforce strict 1.5% max capital stop-loss and reduce position size during high volatility in '{task_name}'."
        elif "syntax" in err_lower or "parse" in err_lower:
            return f"Enforce schema-strict JSON validation and quote escaping prior to serialization in '{task_name}'."
        else:
            return f"Apply pre-execution validation and exception guardrails when invoking '{task_name}' in domain '{domain}'."

    def distill_from_failure(
        self,
        agent_name: str,
        task_name: str,
        error_log: str,
        actions_taken: Optional[str] = None,
        domain: str = "operational",
    ) -> DistilledLesson:
        """Distill a specific failure event into a permanent Universal procedural rule."""
        rule = self.extract_distilled_rule(agent_name, task_name, error_log, domain)
        lesson_id = f"lsn_{uuid.uuid4().hex[:8]}"

        lesson = DistilledLesson(
            id=lesson_id,
            agent_name=agent_name.upper(),
            domain=domain,
            trigger_error=error_log[:200] if error_log else "",
            rule=rule,
            context=actions_taken or "Standard operational pipeline",
            scope=MemoryScope.UNIVERSAL,
            confidence=0.98,
            importance=0.95,
            applied_count=1,
            created_at=time.time(),
        )

        # Save to SQLite lessons_applied ledger
        try:
            with sqlite3.connect(self.fabric.local_db_path, timeout=5.0) as conn:
                c = conn.cursor()
                c.execute("""
                    INSERT OR REPLACE INTO lessons_applied
                    (id, agent_name, domain, trigger_error, rule, context, scope, confidence, importance, applied_count, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    lesson.id,
                    lesson.agent_name,
                    lesson.domain,
                    lesson.trigger_error,
                    lesson.rule,
                    lesson.context,
                    lesson.scope.value,
                    lesson.confidence,
                    lesson.importance,
                    lesson.applied_count,
                    lesson.created_at,
                ))
                conn.commit()
        except Exception as e:
            logger.debug(f"Failed to save distilled lesson: {e}")

        # Also store into fabric as Universal procedural memory
        distilled_content = f"[DISTILLED ECOSYSTEM LESSON - {domain.upper()}] Trigger: {error_log[:100]} | RULE: {rule}"
        self.fabric.record(
            owner_agent=agent_name,
            content_text=distilled_content,
            scope=MemoryScope.UNIVERSAL,
            memory_type="procedural",
            importance=0.95,
            confidence=0.98,
            source="lesson_distiller",
            metadata={"lesson_id": lesson.id, "domain": domain, "task": task_name},
        )

        return lesson

    def get_applied_lessons(self, agent_name: Optional[str] = None, domain: Optional[str] = None) -> List[DistilledLesson]:
        """Query the lessons_applied ledger."""
        lessons = []
        try:
            with sqlite3.connect(self.fabric.local_db_path, timeout=5.0) as conn:
                c = conn.cursor()
                query = "SELECT id, agent_name, domain, trigger_error, rule, context, scope, confidence, importance, applied_count, created_at FROM lessons_applied WHERE 1=1"
                params = []
                if agent_name:
                    query += " AND (agent_name = ? OR scope = 'universal')"
                    params.append(agent_name.upper())
                if domain:
                    query += " AND domain = ?"
                    params.append(domain)
                query += " ORDER BY importance DESC, created_at DESC"
                c.execute(query, params)
                for row in c.fetchall():
                    lessons.append(DistilledLesson(
                        id=row[0],
                        agent_name=row[1],
                        domain=row[2],
                        trigger_error=row[3],
                        rule=row[4],
                        context=row[5],
                        scope=MemoryScope(row[6]),
                        confidence=row[7],
                        importance=row[8],
                        applied_count=row[9],
                        created_at=row[10],
                    ))
        except Exception as e:
            logger.debug(f"Failed to query lessons_applied: {e}")
        return lessons

    def run_nightly_distillation_cycle(self) -> Dict[str, Any]:
        """Run the comprehensive distillation cycle across all raw episodic memory records."""
        distilled_count = 0
        try:
            with sqlite3.connect(self.fabric.local_db_path, timeout=5.0) as conn:
                c = conn.cursor()
                # Find all error memories not yet distilled
                c.execute("""
                    SELECT id, owner_agent, content_text, metadata_json, created_at
                    FROM fabric_memories
                    WHERE content_text LIKE '%Error:%' OR content_text LIKE '%FAILED%' OR content_text LIKE '%FAIL%'
                """)
                rows = c.fetchall()
                for row in rows:
                    owner = row[1]
                    content = row[2]
                    meta = json.loads(row[3]) if row[3] else {}
                    task = meta.get("action", "automated_task")
                    self.distill_from_failure(
                        agent_name=owner,
                        task_name=task,
                        error_log=content,
                        domain="ecosystem_resilience",
                    )
                    distilled_count += 1
        except Exception as e:
            logger.debug(f"Nightly distillation cycle notice: {e}")

        return {
            "status": "COMPLETED",
            "cycle_timestamp": time.time(),
            "distilled_lessons_generated": distilled_count,
            "active_ledger_total": len(self.get_applied_lessons()),
        }


# Singleton instances
fabric = UniversalMemoryFabric()
lesson_distiller = NightlyLessonDistiller(fabric)
