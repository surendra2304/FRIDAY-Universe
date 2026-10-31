"""
Memora Persistent Cognitive Memory Client for Project FORGE.
Connects Forge to the Memora Long-Term Memory Fabric (Cloud & Local Fallback).
Enables Forge agents (Architect, Developer, Orchestrator) to recall prior architectural decisions,
user preferences, and learned engineering patterns, and record new memories.
"""

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

import httpx

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.integrations.memora_outbox import OracleMemoraOutbox, is_oracle_url

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

    Supports asynchronous & synchronous operations with an automatic fallback:
    the ``MEMORA_OUTBOX`` table in the FORGE schema. There is no local SQLite
    spool -- Oracle Autonomous Database is the only durable store.
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
            # Accepted for backwards compatibility only. A local SQLite spool is
            # no longer supported; memories are spooled in Oracle.
            logger.warning(
                "MemoraClient(local_db_path=...) is ignored: FORGE spools memories "
                "in the Oracle MEMORA_OUTBOX table."
            )

        self._oracle_outbox: OracleMemoraOutbox | None = None
        self._backend = "unavailable"

        try:
            database_url = settings.get_database_url()
        except RuntimeError as exc:
            # Agent hot path: memory must degrade to "no memory", never abort a
            # build because the DSN is missing.
            logger.warning("Memora fallback spool unavailable: %s", exc)
        else:
            if is_oracle_url(database_url):
                self._oracle_outbox = OracleMemoraOutbox(database_url)
                self._backend = "oracle"
                logger.info(
                    "Memora fallback spool: Oracle MEMORA_OUTBOX table (FORGE schema)"
                )
            else:
                logger.warning(
                    "Memora fallback spool unavailable: database URL is not Oracle."
                )

    @property
    def local_db_path(self) -> str:
        """Deprecated: always empty; the Oracle outbox replaced the SQLite spool."""
        return ""

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
    # Local Fallback Engine (Oracle MEMORA_OUTBOX)
    # -------------------------------------------------------------------------

    def _record_locally(
        self,
        agent_name: str,
        user_input: str,
        agent_output: str,
        event_type: str,
        tags: list[str] | None,
        metadata: dict[str, Any] | None,
    ) -> dict[str, Any]:
        content = f"Forge Task: {user_input} | Result: {agent_output}"
        if self._oracle_outbox is None:
            return {
                "status": "error",
                "error": "Oracle MEMORA_OUTBOX is not configured; memory was not persisted.",
            }
        try:
            rec_id = self._oracle_outbox.record(
                agent_name=agent_name.lower(),
                memory_type="episodic",
                content_text=content,
                source=f"agent:{agent_name.lower()}",
                importance=0.9,
            )
            return {"id": rec_id, "status": "persisted_locally"}
        except Exception as e:
            logger.warning(f"Oracle MEMORA_OUTBOX memory record failed: {e}")
            return {"status": "error", "error": str(e)}

    def _record_fact_locally(
        self,
        agent_name: str,
        fact_text: str,
        category: str,
        importance: float,
        entities: list[str] | None,
    ) -> dict[str, Any]:
        if self._oracle_outbox is None:
            return {
                "status": "error",
                "error": "Oracle MEMORA_OUTBOX is not configured; fact was not persisted.",
            }
        try:
            rec_id = self._oracle_outbox.record(
                agent_name=agent_name.lower(),
                memory_type="semantic",
                content_text=fact_text,
                source=f"agent:{agent_name.lower()}",
                importance=importance,
            )
            return {"id": rec_id, "status": "fact_persisted_locally"}
        except Exception as e:
            logger.warning(f"Oracle MEMORA_OUTBOX fact record failed: {e}")
            return {"status": "error", "error": str(e)}

    def _keyword_list(self, query: str) -> list[str]:
        """Deduplicated, capped keyword list for keyword-overlap recall.

        One LIKE clause is built per keyword. A hostile or degenerate query -- a
        5 000-character goal, or "app app app ..." repeated 2 000 times --
        produced thousands of clauses (Oracle rejects more than 1 000 elements
        in an OR chain), so recall silently returned nothing for those tasks.
        Deduplicate, keep the most selective (longest) keywords, and cap the
        clause count: past a couple of dozen the extra terms add noise, not
        recall.
        """
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
        return keywords

    def _recall_locally(self, agent_name: str, query: str, limit: int) -> list[dict[str, Any]]:
        try:
            keywords = self._keyword_list(query)
            if not keywords:
                return []

            if self._oracle_outbox is None:
                return []

            rows = self._oracle_outbox.recall(keywords, limit)
            return [MemoryItem(r) for r in rows]
        except Exception as e:
            logger.warning(f"Oracle MEMORA_OUTBOX memory recall failed: {e}")
            return []


# Ceiling on LIKE clauses in a recall query. Oracle rejects an OR chain with
# more than 1 000 elements, and a few dozen keywords already capture recall.
_MAX_RECALL_KEYWORDS = 24

_memora_client_instance: MemoraClient | None = None


def get_memora_client() -> MemoraClient:
    """Return singleton MemoraClient instance."""
    global _memora_client_instance
    if _memora_client_instance is None:
        _memora_client_instance = MemoraClient()
    return _memora_client_instance
