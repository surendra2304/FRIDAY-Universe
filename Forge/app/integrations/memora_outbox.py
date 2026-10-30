"""
Oracle-backed spool for Memora memories that could not be delivered.

Both Forge Memora clients (``app.integrations.memora_client`` and the legacy
``forge_upgrade.memora_client``) used to fall back to a local SQLite file such
as ``/dev/shm/forge_memora.db``. On a VM whose only durable store is Oracle ADB
that spool is lost on restart and invisible to every other agent.

When the active database is Oracle, the spool is instead the ``MEMORA_OUTBOX``
table in the FORGE schema. The table is created by
``DatabaseManager._ensure_schema`` (it is part of ``SCHEMA_SQL_ORACLE``) and,
defensively, on first use here -- the Memora client may write before the API
startup hook has initialised the schema.

The class is deliberately synchronous: the Memora client's storage methods are
plain ``def`` methods invoked from the agent hot path (and from
``asyncio.to_thread``), so they cannot await the async ``DatabaseManager``.
A tiny SQLAlchemy pool is used instead; the URL is derived from the same
``Settings.get_database_url()`` that the async engine uses, so credentials and
ADB connection parameters are shared.
"""

from __future__ import annotations

import threading
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import CLOB, String, bindparam, create_engine, text

from app.core.logging import get_logger
from app.memory.db import MEMORA_OUTBOX_DDL_ORACLE, is_benign_ddl_error

logger = get_logger("integrations.memora_outbox")

OUTBOX_TABLE = "MEMORA_OUTBOX"
OUTBOX_COLUMNS = (
    "id",
    "agent_name",
    "memory_type",
    "content_text",
    "source",
    "confidence",
    "importance",
    "lifecycle_state",
    "tenant_id",
    "created_at",
)


def is_oracle_url(url: str | None) -> bool:
    """True when the SQLAlchemy URL targets Oracle."""
    return bool(url) and "oracle" in str(url).lower()


def to_sync_oracle_url(url: str) -> str:
    """Return the synchronous ``oracle+oracledb://`` form of an async URL."""
    if url.startswith("oracle+oracledb_async://"):
        return "oracle+oracledb://" + url[len("oracle+oracledb_async://") :]
    return url


class OracleMemoraOutbox:
    """Synchronous ``MEMORA_OUTBOX`` reader/writer.

    Every public method is exception-safe in the same way the callers are: a
    storage failure returns an error envelope / empty list rather than aborting
    an engineering step.
    """

    def __init__(self, database_url: str):
        self._sync_url = to_sync_oracle_url(database_url)
        self._engine = None
        self._lock = threading.Lock()
        self._schema_ready = False

    # ------------------------------------------------------------------
    # plumbing
    # ------------------------------------------------------------------

    def _get_engine(self):
        with self._lock:
            if self._engine is None:
                self._engine = create_engine(
                    self._sync_url,
                    pool_pre_ping=True,
                    pool_size=2,
                    max_overflow=2,
                    pool_recycle=1800,
                )
            return self._engine

    def _ensure_schema(self, conn) -> None:
        if self._schema_ready:
            return
        try:
            conn.execute(text(MEMORA_OUTBOX_DDL_ORACLE))
            self._schema_ready = True
        except Exception as exc:
            if is_benign_ddl_error(exc):
                self._schema_ready = True
                return
            raise

    @staticmethod
    def _lower_keys(row: Any) -> dict[str, Any]:
        return {str(k).lower(): v for k, v in dict(row).items()}

    # ------------------------------------------------------------------
    # writes
    # ------------------------------------------------------------------

    def record(
        self,
        *,
        agent_name: str,
        memory_type: str,
        content_text: str,
        source: str | None,
        importance: float,
        confidence: float = 1.0,
    ) -> str:
        """Insert one spooled memory and return its id."""
        record_id = str(uuid.uuid4())
        now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
        stmt = text(
            f"""
            INSERT INTO {OUTBOX_TABLE}
                (id, agent_name, memory_type, content_text, source,
                 confidence, importance, lifecycle_state, tenant_id, created_at)
            VALUES
                (:id, :agent_name, :memory_type, :content_text, :source,
                 :confidence, :importance, 'active', 'default', :created_at)
            """
        ).bindparams(
            # A str longer than 4000 bytes must be bound as a CLOB for Oracle.
            bindparam("content_text", type_=CLOB),
            bindparam("source", type_=String(1024)),
        )
        engine = self._get_engine()
        with engine.begin() as conn:
            self._ensure_schema(conn)
            conn.execute(
                stmt,
                {
                    "id": record_id,
                    "agent_name": (agent_name or "forge")[:128],
                    "memory_type": (memory_type or "episodic")[:64],
                    "content_text": content_text or "",
                    "source": (source or None),
                    "confidence": float(confidence),
                    "importance": float(importance),
                    "created_at": now,
                },
            )
        return record_id

    # ------------------------------------------------------------------
    # reads
    # ------------------------------------------------------------------

    def recall(self, keywords: list[str], limit: int) -> list[dict[str, Any]]:
        """Return spooled memories matching any keyword, best first."""
        if not keywords:
            return []
        clauses: list[str] = []
        binds: dict[str, Any] = {}
        for idx, keyword in enumerate(keywords):
            name = f"k{idx}"
            clauses.append(f"content_text LIKE :{name}")
            binds[name] = f"%{keyword}%"
        binds["row_limit"] = max(int(limit), 1)
        stmt = text(
            f"""
            SELECT id, content_text, memory_type, importance, created_at
            FROM {OUTBOX_TABLE}
            WHERE {" OR ".join(clauses)}
            ORDER BY importance DESC, created_at DESC
            FETCH FIRST :row_limit ROWS ONLY
            """
        )
        engine = self._get_engine()
        with engine.connect() as conn:
            self._ensure_schema(conn)
            rows = conn.execute(stmt, binds).mappings().all()
            conn.commit()
        return [self._lower_keys(row) for row in rows]

    def recent(self, agent_name: str, limit: int = 400) -> list[dict[str, Any]]:
        """Return the most recent memories for one agent (newest first)."""
        stmt = text(
            f"""
            SELECT id, memory_type, content_text, source, importance, created_at
            FROM {OUTBOX_TABLE}
            WHERE agent_name = :agent_name
            ORDER BY created_at DESC
            FETCH FIRST :row_limit ROWS ONLY
            """
        )
        engine = self._get_engine()
        with engine.connect() as conn:
            self._ensure_schema(conn)
            rows = (
                conn.execute(
                    stmt,
                    {
                        "agent_name": (agent_name or "forge")[:128],
                        "row_limit": max(int(limit), 1),
                    },
                )
                .mappings()
                .all()
            )
            conn.commit()
        return [self._lower_keys(row) for row in rows]

    def close(self) -> None:
        with self._lock:
            engine, self._engine = self._engine, None
        if engine is not None:
            engine.dispose()


__all__ = ["OracleMemoraOutbox", "is_oracle_url", "to_sync_oracle_url"]
