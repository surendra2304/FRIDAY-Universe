"""
Memora Persistent Cognitive Memory Client for Project FORGE.
Connects Forge to the Memora Long-Term Memory Fabric (Cloud & Local Fallback).
Enables Forge agents (Architect, Developer, Orchestrator) to recall prior architectural decisions,
user preferences, and learned engineering patterns, and record new memories.
"""

import json
import os
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any

import httpx

from app.core.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger("integrations.memora")


class MemoryItem(dict):
    """
    Dictionary representing a Memora memory record with property accessors
    for seamless compatibility across both dict-style and attribute-style access.
    """

    @property
    def id(self) -> str:
        return str(self.get("id") or self.get("memory_id") or "")

    @property
    def memory_id(self) -> str:
        return self.id

    @property
    def content(self) -> str:
        return str(self.get("content_text") or self.get("content") or "")

    @property
    def content_text(self) -> str:
        return self.content

    @property
    def memory_type(self) -> str:
        return str(self.get("memory_type", "memory"))

    @property
    def similarity(self) -> float:
        val = self.get("similarity")
        if val is None:
            val = self.get("final_score")
        if val is None:
            val = self.get("score")
        try:
            return float(val) if val is not None else 1.0
        except (ValueError, TypeError):
            return 1.0

    def __getattr__(self, name: str) -> Any:
        if name in self:
            return self[name]
        raise AttributeError(f"'MemoryItem' object has no attribute '{name}'")


class MemoraClient:
    """
    Client for interacting with Memora Long-Term Memory Fabric.
    Supports asynchronous & synchronous operations with automatic local SQLite fallback.
    """

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        local_db_path: str | None = None,
        timeout: float = 5.0,
    ):
        settings: Settings = get_settings()
        self.base_url = (base_url or settings.memora_url).rstrip("/")
        self.api_key = api_key or settings.memora_api_key
        self.timeout = timeout

        if local_db_path:
            self.local_db_path = local_db_path
        else:
            cand = Path("d:/FRIDAY Universe/Memora/data/memora.db")
            if cand.exists():
                self.local_db_path = str(cand)
            else:
                self.local_db_path = str(settings.data_dir / "memora.db")

    def _get_headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-Agent-Name": "forge",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
            headers["X-Agent-Key"] = self.api_key
        return headers

    # -------------------------------------------------------------------------
    # Asynchronous Memory Operations
    # -------------------------------------------------------------------------

    async def a_recall_memories(
        self,
        query: str,
        agent_name: str = "forge",
        limit: int = 5,
        threshold: float = 0.0,
    ) -> list[dict[str, Any]]:
        """Asynchronously search and recall persistent memories relevant to a query."""
        if not query or not query.strip():
            return []

        encoded_q = urllib.parse.quote(query.strip())
        url = f"{self.base_url}/v1/memories/search?q={encoded_q}&limit={limit}&min_score={threshold}"
        headers = self._get_headers()

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(url, headers=headers)
                if resp.status_code == 200:
                    results = resp.json()
                    if isinstance(results, list):
                        return [MemoryItem(r) for r in results]
                    elif isinstance(results, dict) and "memories" in results:
                        return [MemoryItem(r) for r in results["memories"]]
        except Exception as e:
            logger.debug(f"Memora cloud async search failed ({e}); querying local fallback DB.")

        return self._recall_locally(agent_name, query, limit)

    async def a_build_context_prompt(
        self,
        query: str,
        agent_name: str = "forge",
        max_memories: int = 5,
    ) -> str:
        """Asynchronously build an injected memory context block for agent reasoning prompts."""
        memories = await self.a_recall_memories(query, agent_name=agent_name, limit=max_memories)
        return self._format_context_prompt(memories)

    async def a_record_interaction(
        self,
        user_input: str,
        agent_output: str,
        agent_name: str = "forge",
        event_type: str = "software_task",
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Asynchronously record an interaction turn or build outcome into Memora."""
        payload = {
            "agent_name": agent_name.lower(),
            "user_text": user_input,
            "agent_text": agent_output,
            "event_type": event_type,
            "tags": tags or ["forge", "autonomous_build"],
            "metadata": metadata or {},
        }
        url = f"{self.base_url}/v1/memories/record-interaction"
        headers = self._get_headers()

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(url, json=payload, headers=headers)
                if resp.status_code in (200, 201):
                    return resp.json()
        except Exception as e:
            logger.debug(f"Memora cloud async record failed ({e}); falling back to local DB.")

        return self._record_locally(agent_name, user_input, agent_output, event_type, tags, metadata)

    async def a_record_fact(
        self,
        fact_text: str,
        agent_name: str = "forge",
        category: str = "preference",
        importance: float = 0.95,
        entities: list[str] | None = None,
    ) -> dict[str, Any]:
        """Asynchronously record an architectural rule, decision, or user preference into Memora."""
        payload = {
            "content_text": fact_text,
            "memory_type": "semantic",
            "source": f"agent:{agent_name.lower()}",
            "confidence": 1.0,
            "importance": importance,
            "provenance": {
                "category": category,
                "entities": entities or ["forge", category],
            },
        }
        url = f"{self.base_url}/v1/memories"
        headers = self._get_headers()

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(url, json=payload, headers=headers)
                if resp.status_code in (200, 201):
                    return resp.json()
        except Exception as e:
            logger.debug(f"Memora cloud async record_fact failed ({e}); falling back to local DB.")

        return self._record_fact_locally(agent_name, fact_text, category, importance, entities)

    # -------------------------------------------------------------------------
    # Synchronous Memory Operations
    # -------------------------------------------------------------------------

    def recall_memories(
        self,
        agent_name: str = "forge",
        query: str = "",
        limit: int = 5,
        threshold: float = 0.0,
    ) -> list[dict[str, Any]]:
        """Synchronously recall memories from Memora."""
        if not query or not query.strip():
            return []

        encoded_q = urllib.parse.quote(query.strip())
        url = f"{self.base_url}/v1/memories/search?q={encoded_q}&limit={limit}&min_score={threshold}"
        headers = self._get_headers()

        try:
            req = urllib.request.Request(url, headers=headers, method="GET")
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                if response.status == 200:
                    results = json.loads(response.read().decode("utf-8"))
                    if isinstance(results, list):
                        return [MemoryItem(r) for r in results]
                    elif isinstance(results, dict) and "memories" in results:
                        return [MemoryItem(r) for r in results["memories"]]
        except Exception as e:
            logger.debug(f"Memora sync search failed ({e}); searching local DB.")

        return self._recall_locally(agent_name, query, limit)

    def build_context_prompt(
        self,
        agent_name: str = "forge",
        query: str = "",
        max_memories: int = 5,
    ) -> str:
        """Synchronously build memory context prompt."""
        memories = self.recall_memories(agent_name=agent_name, query=query, limit=max_memories)
        return self._format_context_prompt(memories)

    def record_interaction(
        self,
        agent_name: str = "forge",
        user_input: str = "",
        agent_output: str = "",
        event_type: str = "software_task",
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Synchronously record an interaction turn into Memora."""
        payload = {
            "agent_name": agent_name.lower(),
            "user_text": user_input,
            "agent_text": agent_output,
            "event_type": event_type,
            "tags": tags or ["forge", "autonomous_build"],
            "metadata": metadata or {},
        }
        url = f"{self.base_url}/v1/memories/record-interaction"
        headers = self._get_headers()

        try:
            req = urllib.request.Request(
                url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST"
            )
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                if response.status in (200, 201):
                    return json.loads(response.read().decode("utf-8"))
        except Exception as e:
            logger.debug(f"Memora sync record failed ({e}); falling back to local DB.")

        return self._record_locally(agent_name, user_input, agent_output, event_type, tags, metadata)

    def record_fact(
        self,
        agent_name: str = "forge",
        fact_text: str = "",
        category: str = "preference",
        importance: float = 0.95,
        entities: list[str] | None = None,
    ) -> dict[str, Any]:
        """Synchronously record a verified fact or user preference into Memora."""
        payload = {
            "content_text": fact_text,
            "memory_type": "semantic",
            "source": f"agent:{agent_name.lower()}",
            "confidence": 1.0,
            "importance": importance,
            "provenance": {
                "category": category,
                "entities": entities or ["forge", category],
            },
        }
        url = f"{self.base_url}/v1/memories"
        headers = self._get_headers()

        try:
            req = urllib.request.Request(
                url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST"
            )
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                if response.status in (200, 201):
                    return json.loads(response.read().decode("utf-8"))
        except Exception as e:
            logger.debug(f"Memora sync record_fact failed ({e}); using local fallback.")

        return self._record_fact_locally(agent_name, fact_text, category, importance, entities)

    # -------------------------------------------------------------------------
    # Context Formatting Helper
    # -------------------------------------------------------------------------

    def _format_context_prompt(self, memories: list[dict[str, Any]]) -> str:
        if not memories:
            return ""

        lines = [
            "[PERSISTENT COGNITIVE MEMORY (MEMORA)] (Memora Cognitive Memory Context):",
            "The following verified memories, user preferences, and engineering conventions were recalled from Memora:",
        ]
        seen = set()
        for m in memories:
            content = (m.get("content_text") or m.get("content") or "").strip()
            if content and content not in seen:
                seen.add(content)
                mtype = m.get("memory_type", "memory").upper()
                lines.append(f"- [{mtype}] {content}")

        lines.append("Apply these learned preferences and past architectural decisions naturally to your implementation.")
        return "\n".join(lines)

    # -------------------------------------------------------------------------
    # Local SQLite Fallback Engine
    # -------------------------------------------------------------------------

    def _ensure_local_tables(self, conn: sqlite3.Connection) -> None:
        c = conn.cursor()
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS agents (
                id TEXT PRIMARY KEY,
                name TEXT UNIQUE,
                role TEXT,
                tenant_id TEXT
            )
            """
        )
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS namespaces (
                id TEXT PRIMARY KEY,
                path TEXT,
                type TEXT,
                agent_id TEXT,
                tenant_id TEXT
            )
            """
        )
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS memory_records (
                id TEXT PRIMARY KEY,
                namespace_id TEXT,
                owner_id TEXT,
                memory_type TEXT,
                content_text TEXT,
                source TEXT,
                confidence REAL,
                importance REAL,
                lifecycle_state TEXT,
                tenant_id TEXT,
                created_at TEXT
            )
            """
        )
        conn.commit()

    def _record_locally(
        self,
        agent_name: str,
        user_input: str,
        agent_output: str,
        event_type: str,
        tags: list[str] | None,
        metadata: dict[str, Any] | None,
    ) -> dict[str, Any]:
        try:
            os.makedirs(os.path.dirname(self.local_db_path), exist_ok=True)
            with sqlite3.connect(self.local_db_path, timeout=5.0) as conn:
                self._ensure_local_tables(conn)
                c = conn.cursor()
                c.execute("SELECT id FROM agents WHERE name = ?", (agent_name.lower(),))
                row = c.fetchone()
                aid = row[0] if row else str(uuid.uuid4())
                if not row:
                    c.execute(
                        "INSERT INTO agents (id, name, role, tenant_id) VALUES (?, ?, ?, ?)",
                        (aid, agent_name.lower(), "worker", "default"),
                    )

                c.execute("SELECT id FROM namespaces WHERE agent_id = ?", (aid,))
                row_ns = c.fetchone()
                nid = row_ns[0] if row_ns else str(uuid.uuid4())
                if not row_ns:
                    c.execute(
                        "INSERT INTO namespaces (id, path, type, agent_id, tenant_id) VALUES (?, ?, ?, ?, ?)",
                        (nid, f"memora://{agent_name.lower()}/private", "agent-private", aid, "default"),
                    )

                now_iso = time.strftime("%Y-%m-%d %H:%M:%S")
                rec_id = str(uuid.uuid4())
                content = f"Forge Task: {user_input} | Result: {agent_output}"
                cols = {col[1] for col in c.execute("PRAGMA table_info(memory_records)").fetchall()}
                record_data = {
                    "id": rec_id,
                    "namespace_id": nid,
                    "owner_id": aid,
                    "agent_id": aid,
                    "user_id": "default",
                    "workspace_id": "default",
                    "device_id": "default",
                    "memory_type": "episodic",
                    "content_text": content,
                    "source": f"agent:{agent_name.lower()}",
                    "confidence": 1.0,
                    "importance": 0.9,
                    "lifecycle_state": "active",
                    "tenant_id": "default",
                    "observed_at": now_iso,
                    "created_at": now_iso,
                }
                valid_fields = [k for k in record_data if k in cols]
                placeholders = ", ".join(["?"] * len(valid_fields))
                col_names = ", ".join(valid_fields)
                c.execute(
                    f"INSERT INTO memory_records ({col_names}) VALUES ({placeholders})",
                    [record_data[k] for k in valid_fields],
                )
                conn.commit()
                return {"id": rec_id, "status": "persisted_locally"}
        except Exception as e:
            logger.warning(f"Local SQLite memory record failed: {e}")
            return {"status": "error", "error": str(e)}

    def _record_fact_locally(
        self,
        agent_name: str,
        fact_text: str,
        category: str,
        importance: float,
        entities: list[str] | None,
    ) -> dict[str, Any]:
        try:
            os.makedirs(os.path.dirname(self.local_db_path), exist_ok=True)
            with sqlite3.connect(self.local_db_path, timeout=5.0) as conn:
                self._ensure_local_tables(conn)
                c = conn.cursor()
                c.execute("SELECT id FROM agents WHERE name = ?", (agent_name.lower(),))
                row = c.fetchone()
                aid = row[0] if row else str(uuid.uuid4())
                c.execute("SELECT id FROM namespaces WHERE agent_id = ?", (aid,))
                row_ns = c.fetchone()
                nid = row_ns[0] if row_ns else str(uuid.uuid4())
                now_iso = time.strftime("%Y-%m-%d %H:%M:%S")
                rec_id = str(uuid.uuid4())
                cols = {col[1] for col in c.execute("PRAGMA table_info(memory_records)").fetchall()}
                record_data = {
                    "id": rec_id,
                    "namespace_id": nid,
                    "owner_id": aid,
                    "agent_id": aid,
                    "user_id": "default",
                    "workspace_id": "default",
                    "device_id": "default",
                    "memory_type": "semantic",
                    "content_text": fact_text,
                    "source": f"agent:{agent_name.lower()}",
                    "confidence": 1.0,
                    "importance": importance,
                    "lifecycle_state": "active",
                    "tenant_id": "default",
                    "observed_at": now_iso,
                    "created_at": now_iso,
                }
                valid_fields = [k for k in record_data if k in cols]
                placeholders = ", ".join(["?"] * len(valid_fields))
                col_names = ", ".join(valid_fields)
                c.execute(
                    f"INSERT INTO memory_records ({col_names}) VALUES ({placeholders})",
                    [record_data[k] for k in valid_fields],
                )
                conn.commit()
                return {"id": rec_id, "status": "fact_persisted_locally"}
        except Exception as e:
            logger.warning(f"Local SQLite fact record failed: {e}")
            return {"status": "error", "error": str(e)}

    def _recall_locally(self, agent_name: str, query: str, limit: int) -> list[dict[str, Any]]:
        if not os.path.exists(self.local_db_path):
            return []
        try:
            with sqlite3.connect(self.local_db_path, timeout=5.0) as conn:
                conn.row_factory = sqlite3.Row
                c = conn.cursor()
                # One LIKE clause per keyword. A hostile or degenerate query --
                # a 5 000-character goal, or "app app app ..." repeated 2 000 times
                # -- produced thousands of clauses and SQLite rejected the whole
                # statement with "Expression tree is too large (maximum depth
                # 1000)", so recall silently returned nothing for those tasks.
                # Deduplicate, keep the most selective (longest) keywords, and cap
                # the clause count: past a couple of dozen the extra terms add
                # noise, not recall.
                raw_keywords = [k.strip() for k in query.split() if len(k.strip()) > 3]
                seen: set[str] = set()
                keywords = []
                for kw in sorted(set(raw_keywords), key=len, reverse=True):
                    low = kw.lower()
                    if low in seen:
                        continue
                    seen.add(low)
                    keywords.append(kw)
                    if len(keywords) >= _MAX_RECALL_KEYWORDS:
                        break
                if not keywords:
                    fallback = (query or "").strip()
                    keywords = [fallback[:_MAX_RECALL_KEYWORDS * 8]] if fallback else []
                if not keywords:
                    return []
                like_clauses = " OR ".join(["content_text LIKE ?" for _ in keywords])
                params = [f"%{k}%" for k in keywords]
                query_sql = f"""
                    SELECT id, content_text, memory_type, importance, created_at
                    FROM memory_records
                    WHERE {like_clauses}
                    ORDER BY importance DESC, created_at DESC
                    LIMIT ?
                """
                c.execute(query_sql, (*params, limit))
                rows = c.fetchall()
                return [MemoryItem(dict(r)) for r in rows]
        except Exception as e:
            logger.warning(f"Local SQLite memory recall failed: {e}")
            return []


# Ceiling on LIKE clauses in a recall query. SQLite refuses a
# statement whose expression tree is deeper than 1000, so an
# unbounded keyword list silently returns nothing.
_MAX_RECALL_KEYWORDS = 24

_memora_client_instance: MemoraClient | None = None


def get_memora_client() -> MemoraClient:
    """Return singleton MemoraClient instance."""
    global _memora_client_instance
    if _memora_client_instance is None:
        _memora_client_instance = MemoraClient()
    return _memora_client_instance
