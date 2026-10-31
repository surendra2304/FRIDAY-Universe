"""
Universal Memora Client for Forge Autonomous Software Engineering.

This module is the self-brain's storage layer. It previously shipped a fallback
client that was dead in three separate ways:

  * ``build_self_upgrade_context`` and ``learn_from_outcome`` did not exist at
    all, so ``BaseAgent.prompt_model`` raised ``AttributeError`` on every single
    agent prompt. The call site swallows the exception, so the failure was
    invisible -- agents simply never received learned guidance.
  * ``recall_memories`` was hardcoded to ``return []``.
  * ``local_db_path`` pointed at ``d:/FRIDAY Universe/Memora/data/memora.db``, a
    Windows path that does not exist anywhere else, so ``record_interaction``
    returned before writing anything.

Verified broken before the fix (``/tmp/memora_probe.py``): 6 of 8 public methods
raised ``AttributeError``; the two that did not returned ``None`` and ``[]``
respectively without touching any storage.

The fallback now persists to a portable location and shares the canonical Memora
schema (agents / namespaces / memory_records) with
``app.integrations.memora_client``, so a lesson written by either client is
readable by the other. When the active database is Oracle Autonomous Database the
fallback is the ``MEMORA_OUTBOX`` table in the FORGE schema instead of a SQLite
file (nothing under ``/dev/shm`` survives an ADB-only deployment).
Every public method is exception-safe: callers in the
agent hot path do not all guard these calls, so a storage failure must degrade
to "no memory" rather than abort an engineering step.
"""

from __future__ import annotations

import asyncio
import re
import sys
from pathlib import Path
from typing import Any

# The Oracle spool is optional: `forge_upgrade` is also imported standalone.
try:
    from app.core.config import get_settings as _get_settings
    from app.integrations.memora_outbox import OracleMemoraOutbox as _OracleMemoraOutbox
    from app.integrations.memora_outbox import is_oracle_url as _is_oracle_url
except Exception:  # pragma: no cover - standalone use
    _get_settings = None  # type: ignore[assignment]
    _OracleMemoraOutbox = None  # type: ignore[assignment]
    _is_oracle_url = None  # type: ignore[assignment]

# Try importing from central Memora SDK first. When the real fabric is present
# it wins; the local fallback below only runs when it is not.
try:
    MEMORA_ROOT = Path("d:/FRIDAY Universe/Memora")
    if str(MEMORA_ROOT) not in sys.path:
        sys.path.insert(0, str(MEMORA_ROOT))
    from sdk.memora_client import memora_client  # type: ignore  # noqa: F401

    _USING_SDK = True
except Exception:
    _USING_SDK = False

    # Tokens too common to be useful for retrieval.
    _STOPWORDS = frozenset(
        """a an and are as at be by for from has have i in into is it its of on or
        that the their there these this to was were will with you your we our""".split()
    )

    class MemoraClient:
        """Local, portable Memora client with real persistence and retrieval."""

        def __init__(self, db_path: str | Path | None = None):
            self._explicit_sqlite = db_path is not None or bool(
                os.environ.get("MEMORA_DB_PATH")
            )
            if db_path is not None:
                self.local_db_path = Path(db_path)
            else:
                env = os.environ.get("MEMORA_DB_PATH")
                if env:
                    self.local_db_path = Path(env)
                else:
                    # <repo>/data/memora.db -- portable, and the same file the
                    # app.integrations client uses, so memories are shared.
                    self.local_db_path = (
                        Path(__file__).resolve().parents[1] / "data" / "memora.db"
                    )
            self._schema_ready = False
            self._oracle = None
            if not self._explicit_sqlite:
                url = None
                try:
                    if _get_settings is not None:
                        url = _get_settings().get_database_url()
                except Exception:
                    url = None
                if url and _is_oracle_url is not None and _is_oracle_url(url) and _OracleMemoraOutbox:
                    self._oracle = _OracleMemoraOutbox(url)

        # ------------------------------------------------------------------
        # storage plumbing
        # ------------------------------------------------------------------

        def _connect(self) -> sqlite3.Connection:
            self.local_db_path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(str(self.local_db_path), timeout=5.0)
            conn.row_factory = sqlite3.Row
            if not self._schema_ready:
                conn.executescript(_SCHEMA)
                self._schema_ready = True
            return conn

        def _agent_and_namespace(self, conn: sqlite3.Connection, agent_name: str) -> tuple[str, str]:
            """Resolve (agent_id, namespace_id), creating them on first use."""
            row = conn.execute(
                "SELECT id FROM agents WHERE name = ?", (agent_name,)
            ).fetchone()
            if row:
                aid = row[0]
            else:
                aid = str(uuid.uuid4())
                conn.execute(
                    "INSERT INTO agents (id, name, role, tenant_id) VALUES (?, ?, ?, ?)",
                    (aid, agent_name, "forge", "default"),
                )
            ns = conn.execute(
                "SELECT id FROM namespaces WHERE agent_id = ?", (aid,)
            ).fetchone()
            if ns:
                nid = ns[0]
            else:
                nid = str(uuid.uuid4())
                conn.execute(
                    "INSERT INTO namespaces (id, path, type, agent_id, tenant_id)"
                    " VALUES (?, ?, ?, ?, ?)",
                    (nid, f"/{agent_name}", "experience", aid, "default"),
                )
            return aid, nid

        @staticmethod
        def _tokenize(text: str) -> list[str]:
            raw = re.split(r"[^A-Za-z0-9_+#.-]+", (text or "").lower())
            return [t for t in raw if len(t) > 2 and t not in _STOPWORDS]

        # ------------------------------------------------------------------
        # writes
        # ------------------------------------------------------------------

        def record_interaction(
            self,
            agent_name: str,
            user_input: str,
            agent_output: str,
            event_type: str = "software_task",
            tags: list[str] | None = None,
            metadata: dict[str, Any] | None = None,
        ) -> str | None:
            """Persist an episodic memory. Returns the record id, or None."""
            try:
                content = f"{user_input} | {agent_output}"
                if tags:
                    content = f"{content} | tags: {','.join(str(t) for t in tags)}"
                return self._insert(
                    agent_name=agent_name,
                    memory_type=event_type or "episodic",
                    content_text=content,
                    importance=0.6,
                    metadata=metadata,
                )
            except Exception:
                return None

        def record_fact(
            self,
            fact_text: str,
            agent_name: str = "forge",
            category: str = "semantic",
            importance: float = 0.8,
            entities: list[str] | None = None,
            metadata: dict[str, Any] | None = None,
        ) -> str | None:
            """Persist a semantic fact (a durable lesson or convention)."""
            try:
                return self._insert(
                    agent_name=agent_name,
                    memory_type=category or "semantic",
                    content_text=fact_text,
                    importance=float(importance),
                    entities=entities,
                    metadata=metadata,
                )
            except Exception:
                return None

        def learn_from_outcome(
            self,
            agent_name: str = "forge",
            task_name: str = "",
            status: str = "success",
            error_log: str | None = None,
            actions_taken: str | None = None,
            domain: str = "code_synthesis",
            metadata: dict[str, Any] | None = None,
        ) -> str | None:
            """Record the outcome of a unit of work so future runs can use it.

            Failures are stored at higher importance than successes: they are the
            lessons that actually change behaviour, and ``build_self_upgrade_context``
            weights them accordingly.
            """
            try:
                ok = str(status).lower() in {"success", "ok", "passed", "complete"}
                parts = [f"task={task_name}", f"status={status}"]
                if actions_taken:
                    parts.append(f"actions={actions_taken}")
                if error_log:
                    # Keep the tail: the exception message is the useful part.
                    parts.append(f"error={str(error_log)[-400:]}")
                parts.append(f"domain={domain}")
                return self._insert(
                    agent_name=agent_name,
                    memory_type="lesson_failure" if not ok else "lesson_success",
                    content_text=" | ".join(parts),
                    importance=0.9 if not ok else 0.55,
                    metadata=metadata,
                )
            except Exception:
                return None

        def _insert(
            self,
            agent_name: str,
            memory_type: str,
            content_text: str,
            importance: float,
            entities: list[str] | None = None,
            metadata: dict[str, Any] | None = None,
        ) -> str | None:
            rid = str(uuid.uuid4())
            now = time.strftime("%Y-%m-%d %H:%M:%S")
            source = "agent:forge"
            if entities:
                source = f"{source}:{','.join(str(e) for e in entities)}"
            if self._oracle is not None:
                return self._oracle.record(
                    agent_name=agent_name or "forge",
                    memory_type=memory_type,
                    content_text=content_text,
                    source=source,
                    importance=float(importance),
                )
            with self._connect() as conn:
                aid, nid = self._agent_and_namespace(conn, agent_name or "forge")
                conn.execute(
                    "INSERT INTO memory_records (id, namespace_id, owner_id,"
                    " memory_type, content_text, source, confidence, importance,"
                    " lifecycle_state, tenant_id, created_at)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        rid, nid, aid, memory_type, content_text, source,
                        1.0, importance, "active", "default", now,
                    ),
                )
                conn.commit()
            return rid

        # ------------------------------------------------------------------
        # reads
        # ------------------------------------------------------------------

        def recall_memories(
            self,
            agent_name: str,
            query: str,
            limit: int = 5,
            domain: str | None = None,
        ) -> list[dict[str, Any]]:
            """Return memories relevant to ``query``, best first.

            Relevance is keyword overlap against the stored text plus the
            entities recorded on write, tie-broken by importance then recency.
            An empty query returns the most important recent memories.
            """
            try:
                if self._oracle is not None:
                    rows = self._oracle.recent(agent_name or "forge", 400)
                else:
                    with self._connect() as conn:
                        rows = conn.execute(
                            "SELECT m.id, m.memory_type, m.content_text, m.source,"
                            " m.importance, m.created_at"
                            " FROM memory_records m"
                            " JOIN agents a ON a.id = m.owner_id"
                            " WHERE a.name = ? AND m.lifecycle_state = 'active'"
                            " ORDER BY m.created_at DESC LIMIT 400",
                            (agent_name or "forge",),
                        ).fetchall()

                tokens = self._tokenize(query)
                scored: list[tuple[float, dict[str, Any]]] = []
                for row in rows:
                    text = (row["content_text"] or "").lower()
                    entities = [
                        e.lower()
                        for e in (row["source"] or "").split(":")[-1].split(",")
                        if e
                    ]
                    score = 0.0
                    for tok in tokens:
                        if tok in text:
                            score += 1.0
                        if tok in entities:
                            score += 0.5
                    if not tokens:
                        score = float(row["importance"] or 0.0)
                    if score <= 0:
                        continue
                    if domain and domain not in text:
                        score *= 0.5
                    scored.append(
                        (
                            score + float(row["importance"] or 0.0) * 0.1,
                            {
                                "id": row["id"],
                                "memory_type": row["memory_type"],
                                "content_text": row["content_text"],
                                "similarity": round(score, 3),
                                "importance": row["importance"],
                                "created_at": row["created_at"],
                            },
                        )
                    )
                scored.sort(key=lambda item: item[0], reverse=True)
                return [item[1] for item in scored[:limit]]
            except Exception:
                return []

        def build_self_upgrade_context(
            self,
            agent_name: str,
            query: str,
            domain: str = "code_synthesis",
            limit: int = 6,
        ) -> str:
            """Build the guidance block injected into every agent system prompt.

            Failures come first: the point of this block is to stop the engine
            repeating a mistake it has already made. Returns "" when there is
            nothing useful to say, which callers treat as "no memory".
            """
            try:
                memories = self.recall_memories(
                    agent_name=agent_name, query=query, limit=limit, domain=domain
                )
                if not memories:
                    return ""
                failures = [m for m in memories if "failure" in (m["memory_type"] or "")]
                others = [m for m in memories if m not in failures]
                lines: list[str] = []
                if failures:
                    lines.append("Known failure modes to avoid (learned from prior runs):")
                    for m in failures:
                        lines.append(f"- {m['content_text']}")
                if others:
                    lines.append("Relevant prior experience:")
                    for m in others:
                        lines.append(f"- {m['content_text']}")
                if not lines:
                    return ""
                return (
                    "[MEMORA SELF-UPGRADE CONTEXT]\n"
                    + "\n".join(lines)
                    + "\nApply these lessons; do not repeat a recorded failure."
                )
            except Exception:
                return ""

        def build_context_prompt(
            self, query: str, agent_name: str = "forge", limit: int = 5
        ) -> str:
            return self.build_self_upgrade_context(
                agent_name=agent_name, query=query, limit=limit
            )

        # ------------------------------------------------------------------
        # async surface used by the agent roles
        # ------------------------------------------------------------------

        async def a_record_interaction(
            self,
            user_input: str,
            agent_output: str,
            agent_name: str = "forge",
            event_type: str = "software_task",
            tags: list[str] | None = None,
            metadata: dict[str, Any] | None = None,
        ) -> dict[str, Any]:
            rid = await asyncio.to_thread(
                self.record_interaction,
                agent_name, user_input, agent_output, event_type, tags, metadata,
            )
            return {"id": rid, "status": "persisted_locally" if rid else "dropped"}

        async def a_record_fact(
            self,
            fact_text: str,
            agent_name: str = "forge",
            category: str = "semantic",
            importance: float = 0.8,
            entities: list[str] | None = None,
            metadata: dict[str, Any] | None = None,
        ) -> dict[str, Any]:
            rid = await asyncio.to_thread(
                self.record_fact,
                fact_text, agent_name, category, importance, entities, metadata,
            )
            return {"id": rid, "status": "fact_persisted_locally" if rid else "dropped"}

        async def a_recall_memories(
            self,
            query: str,
            agent_name: str = "forge",
            limit: int = 5,
            domain: str | None = None,
        ) -> list[dict[str, Any]]:
            return await asyncio.to_thread(
                self.recall_memories, agent_name, query, limit, domain
            )

        async def a_recall(
            self, query: str, agent_name: str = "forge", limit: int = 5
        ) -> list[dict[str, Any]]:
            return await self.a_recall_memories(query, agent_name=agent_name, limit=limit)

        async def a_build_context_prompt(
            self,
            query: str,
            agent_name: str = "forge",
            limit: int = 5,
            domain: str = "code_synthesis",
        ) -> str:
            return await asyncio.to_thread(
                self.build_self_upgrade_context, agent_name, query, domain, limit
            )

        async def a_learn_from_outcome(self, **kwargs: Any) -> str | None:
            return await asyncio.to_thread(self.learn_from_outcome, **kwargs)


if _USING_SDK:
    # The real Memora fabric is importable; keep the module-level singleton the
    # callers expect but make sure the methods the engine needs are present.
    if not hasattr(memora_client, "build_self_upgrade_context"):
        memora_client.build_self_upgrade_context = (  # type: ignore[attr-defined]
            lambda agent_name, query, domain="code_synthesis", limit=6, _c=memora_client: (
                _c.build_context_prompt(query=query, agent_name=agent_name, limit=limit)
                if hasattr(_c, "build_context_prompt")
                else ""
            )
        )
else:
    memora_client = MemoraClient()

__all__ = ["MemoraClient", "memora_client"]
