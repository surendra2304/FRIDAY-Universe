"""Durable store for FRIDAY's console conversation history (TASK-REL-029).

Until this module existed, the transcript served by
``GET /api/v1/conversation/history`` lived only in an in-memory
``deque(maxlen=10000)`` inside the FRIDAY process (TASK-REL-023 finding):
every restart — including every deploy — wiped the owner's conversation
history entirely, and the console restore could only return what the
current process still held.

This store is the durable counterpart, built on the persistence layer
FRIDAY already runs in production:

* **Production backend: Oracle Autonomous Database**, via the shared
  engine and the ``conversation_history`` table declared in
  :mod:`friday.core.oracle` (created idempotently by ``ensure_schema``).
  FRIDAY persists every durable store to that schema; SQLite is test-only
  by a mechanical gate (:func:`friday.core.oracle.ephemeral_backend_allowed`)
  and no new dependency (Redis/Qdrant/…) is introduced.
* **Test backend: a local SQLite file**, only when a ``db_path`` is passed
  explicitly inside a test run — the same sanctioned shape as
  :class:`friday.agent.execution_trace.ExecutionTraceStore`.

Semantics:

* Writes are synchronous write-through calls; the async wrappers run them
  via :func:`asyncio.to_thread` so the event loop never blocks on the DB.
* A failed write never fails the conversation: methods return ``False``
  and log a warning, and the caller keeps the entry in memory and retries
  it on the next write (the ExecutionTraceStore fail-safe pattern — a
  transiently unreachable database degrades persistence for the session
  instead of breaking the chat it serves).
* Growth is bounded at :data:`MAX_HISTORY_ENTRIES` rows — the durable
  equivalent of the deque's ``maxlen`` — enforced on every insert.
* One row per history entry, keyed by the entry's UUID (``entry_id``).
  Ordering is the identity column ``id`` (insertion order), which mirrors
  the deque's appendleft order exactly; timestamps are payload, not keys.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from sqlalchemy import delete, insert, select, text, update

from friday.core import oracle
from friday.core.exceptions import PersistenceConfigError, PersistenceError
from friday.core.logging import get_logger

logger = get_logger("api.history_store")

#: Durable cap, mirroring ``deque(maxlen=10000)`` in friday.api.server.
MAX_HISTORY_ENTRIES = 10000


def _row_from_entry(entry: dict[str, Any]) -> dict[str, Any]:
    """Normalise a ConversationEntry-shaped dict into a store row."""
    return {
        "entry_id": entry["id"],
        "entry_ts": entry.get("timestamp") or "",
        "user_input": entry.get("user_input") or "",
        "friday_reply": entry.get("friday_reply") or "",
        "input_type": entry.get("input_type") or "text",
        "entry_status": entry.get("status") or "success",
        "agents_json": json.dumps(entry.get("agents_involved") or [], default=str),
        "metadata_json": json.dumps(entry.get("metadata") or {}, default=str),
    }


def _entry_from_row(row: dict[str, Any]) -> dict[str, Any]:
    """Rebuild a ConversationEntry-shaped dict from a store row.

    Oracle stores ``''`` as ``NULL``, so text fields normalise back to
    ``""`` here (``friday_reply`` is legitimately empty for pending turns).
    """
    try:
        agents = json.loads(row.get("agents_json") or "[]")
        if not isinstance(agents, list):
            agents = []
    except (TypeError, ValueError):
        agents = []
    try:
        metadata = json.loads(row.get("metadata_json") or "{}")
        if not isinstance(metadata, dict):
            metadata = {}
    except (TypeError, ValueError):
        metadata = {}
    return {
        "id": row.get("entry_id"),
        "timestamp": row.get("entry_ts") or "",
        "user_input": row.get("user_input") or "",
        "friday_reply": row.get("friday_reply") or "",
        "input_type": row.get("input_type") or "text",
        "status": row.get("entry_status") or "success",
        "agents_involved": agents,
        "metadata": metadata,
    }


class ConversationHistoryStore:
    """Write-through durable store for console conversation-history entries."""

    def __init__(
        self,
        db_path: str | None = None,
        *,
        dsn: str | None = None,
    ) -> None:
        self.db_path = db_path
        self._backend = "sqlite" if db_path else "oracle"
        self._oracle_engine: Any | None = None
        self._oracle_dsn = dsn
        self._oracle_disabled = False

        if db_path:
            if not oracle.ephemeral_backend_allowed():
                raise PersistenceConfigError(
                    "ConversationHistoryStore(db_path=...) is test-only; omit "
                    "db_path so history is written to Oracle Autonomous Database."
                )
            self._init_sqlite()

    # ------------------------------------------------------------------
    # Backend plumbing
    # ------------------------------------------------------------------
    @property
    def backend(self) -> str:
        """Active storage backend: ``oracle`` or ``sqlite``."""
        return self._backend

    def _ensure_oracle(self) -> Any | None:
        """Resolve the shared Oracle engine lazily (never at import time)."""
        if self._oracle_disabled:
            return None
        if self._oracle_engine is None:
            try:
                self._oracle_engine = oracle.get_engine(self._oracle_dsn)
            except PersistenceConfigError:
                if not oracle.ephemeral_backend_allowed():
                    raise
                logger.warning(
                    "No Oracle DSN configured; conversation history is not "
                    "persisted because this process is a test run."
                )
                self._oracle_disabled = True
                return None
            except PersistenceError as pe:
                # Fail-safe (same contract as ExecutionTraceStore): a DSN may
                # be configured while the database itself is unreachable.
                # History persistence must never break the chat it serves —
                # degrade to no-persistence for this process instead.
                logger.warning(
                    "Oracle unreachable for conversation history (%s); history "
                    "is not persisted this session. Chat continues in-memory.",
                    pe,
                )
                self._oracle_disabled = True
                return None
        return self._oracle_engine

    def _init_sqlite(self) -> None:
        """Create the conversation_history table in a test-only SQLite file."""
        from friday.core.database import get_db_connection

        with get_db_connection(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS conversation_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    entry_id TEXT NOT NULL UNIQUE,
                    entry_ts TEXT NOT NULL,
                    user_input TEXT,
                    friday_reply TEXT,
                    input_type TEXT,
                    entry_status TEXT,
                    agents_json TEXT,
                    metadata_json TEXT
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS ix_conv_hist_ts "
                "ON conversation_history(entry_ts)"
            )

    # ------------------------------------------------------------------
    # Synchronous writes (run via asyncio.to_thread from async callers)
    # ------------------------------------------------------------------
    def insert_entry(self, entry: dict[str, Any]) -> bool:
        """Insert one entry and enforce the growth cap. True on success."""
        row = _row_from_entry(entry)
        if self._backend == "sqlite":
            return self._sqlite_insert(row)
        return self._oracle_insert(row)

    def update_entry(self, entry: dict[str, Any]) -> bool:
        """Update the row for ``entry['id']``. False if absent or failed."""
        row = _row_from_entry(entry)
        if self._backend == "sqlite":
            return self._sqlite_update(row)
        return self._oracle_update(row)

    def upsert_entry(self, entry: dict[str, Any]) -> bool:
        """Update if present, insert otherwise (finalize/retry path)."""
        if self.update_entry(entry):
            return True
        return self.insert_entry(entry)

    def delete_all(self) -> bool:
        """Remove every stored entry (the DELETE history endpoint)."""
        if self._backend == "sqlite":
            return self._sqlite_delete_all()
        return self._oracle_delete_all()

    def load_recent(self, limit: int = MAX_HISTORY_ENTRIES) -> list[dict[str, Any]] | None:
        """Return up to ``limit`` entries, newest first.

        Returns ``None`` (not ``[]``) when the store could not be read, so
        callers can tell "empty store" apart from "store unavailable" and
        retry hydration later instead of concluding history is empty.
        """
        if self._backend == "sqlite":
            rows = self._sqlite_load(limit)
        else:
            rows = self._oracle_load(limit)
        if rows is None:
            return None
        return [_entry_from_row(r) for r in rows]

    # ------------------------------------------------------------------
    # Async wrappers — the event loop never blocks on the database
    # ------------------------------------------------------------------
    async def insert_entry_async(self, entry: dict[str, Any]) -> bool:
        return await asyncio.to_thread(self.insert_entry, entry)

    async def update_entry_async(self, entry: dict[str, Any]) -> bool:
        return await asyncio.to_thread(self.update_entry, entry)

    async def upsert_entry_async(self, entry: dict[str, Any]) -> bool:
        return await asyncio.to_thread(self.upsert_entry, entry)

    async def delete_all_async(self) -> bool:
        return await asyncio.to_thread(self.delete_all)

    async def load_recent_async(
        self, limit: int = MAX_HISTORY_ENTRIES
    ) -> list[dict[str, Any]] | None:
        return await asyncio.to_thread(self.load_recent, limit)

    # ------------------------------------------------------------------
    # Oracle backend
    # ------------------------------------------------------------------
    def _oracle_insert(self, row: dict[str, Any]) -> bool:
        engine = self._ensure_oracle()
        if engine is None:
            return False
        table = oracle.conversation_history_table
        try:
            with engine.begin() as conn:
                conn.execute(
                    insert(table).values(
                        entry_id=row["entry_id"],
                        entry_ts=row["entry_ts"],
                        user_input=oracle.nullif_empty(row["user_input"]),
                        friday_reply=oracle.nullif_empty(row["friday_reply"]),
                        input_type=row["input_type"],
                        entry_status=row["entry_status"],
                        agents_json=row["agents_json"],
                        metadata_json=row["metadata_json"],
                    )
                )
                self._trim_oracle(conn)
            return True
        except Exception as exc:
            logger.warning("Failed to insert conversation history to Oracle: %s", exc)
            return False

    def _oracle_update(self, row: dict[str, Any]) -> bool:
        engine = self._ensure_oracle()
        if engine is None:
            return False
        table = oracle.conversation_history_table
        try:
            with engine.begin() as conn:
                result = conn.execute(
                    update(table)
                    .where(table.c.entry_id == row["entry_id"])
                    .values(
                        entry_ts=row["entry_ts"],
                        user_input=oracle.nullif_empty(row["user_input"]),
                        friday_reply=oracle.nullif_empty(row["friday_reply"]),
                        input_type=row["input_type"],
                        entry_status=row["entry_status"],
                        agents_json=row["agents_json"],
                        metadata_json=row["metadata_json"],
                    )
                )
                return int(result.rowcount or 0) > 0
        except Exception as exc:
            logger.warning("Failed to update conversation history in Oracle: %s", exc)
            return False

    def _oracle_delete_all(self) -> bool:
        engine = self._ensure_oracle()
        if engine is None:
            return False
        table = oracle.conversation_history_table
        try:
            with engine.begin() as conn:
                conn.execute(delete(table))
            return True
        except Exception as exc:
            logger.warning("Failed to clear conversation history in Oracle: %s", exc)
            return False

    def _oracle_load(self, limit: int) -> list[dict[str, Any]] | None:
        engine = self._ensure_oracle()
        if engine is None:
            return None
        table = oracle.conversation_history_table
        try:
            with engine.connect() as conn:
                result = conn.execute(
                    select(table).order_by(table.c.id.desc()).limit(limit)
                )
                return [dict(r) for r in result.mappings().fetchall()]
        except Exception as exc:
            logger.warning("Failed to load conversation history from Oracle: %s", exc)
            return None

    @staticmethod
    def _trim_oracle(conn: Any) -> None:
        """Keep at most MAX_HISTORY_ENTRIES rows (identity-ordered).

        Identity values may have gaps (sequence caching), so the invariant
        is a row-count bound, not an exact id window: everything at or below
        ``max(id) - cap`` goes, which can never leave more than ``cap`` rows.
        """
        conn.execute(
            text(
                "DELETE FROM conversation_history "
                "WHERE id <= (SELECT COALESCE(MAX(id), 0) FROM conversation_history) - :cap"
            ),
            {"cap": MAX_HISTORY_ENTRIES},
        )

    # ------------------------------------------------------------------
    # SQLite backend (test-only)
    # ------------------------------------------------------------------
    def _sqlite_insert(self, row: dict[str, Any]) -> bool:
        from friday.core.database import get_db_connection

        try:
            with get_db_connection(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT INTO conversation_history (
                        entry_id, entry_ts, user_input, friday_reply,
                        input_type, entry_status, agents_json, metadata_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row["entry_id"],
                        row["entry_ts"],
                        row["user_input"],
                        row["friday_reply"],
                        row["input_type"],
                        row["entry_status"],
                        row["agents_json"],
                        row["metadata_json"],
                    ),
                )
                conn.execute(
                    "DELETE FROM conversation_history WHERE id <= "
                    "(SELECT COALESCE(MAX(id), 0) FROM conversation_history) - ?",
                    (MAX_HISTORY_ENTRIES,),
                )
                conn.commit()
            return True
        except Exception as exc:
            logger.warning("Failed to insert conversation history to SQLite: %s", exc)
            return False

    def _sqlite_update(self, row: dict[str, Any]) -> bool:
        from friday.core.database import get_db_connection

        try:
            with get_db_connection(self.db_path) as conn:
                cur = conn.execute(
                    """
                    UPDATE conversation_history SET
                        entry_ts = ?, user_input = ?, friday_reply = ?,
                        input_type = ?, entry_status = ?,
                        agents_json = ?, metadata_json = ?
                    WHERE entry_id = ?
                    """,
                    (
                        row["entry_ts"],
                        row["user_input"],
                        row["friday_reply"],
                        row["input_type"],
                        row["entry_status"],
                        row["agents_json"],
                        row["metadata_json"],
                        row["entry_id"],
                    ),
                )
                conn.commit()
                return (cur.rowcount or 0) > 0
        except Exception as exc:
            logger.warning("Failed to update conversation history in SQLite: %s", exc)
            return False

    def _sqlite_delete_all(self) -> bool:
        from friday.core.database import get_db_connection

        try:
            with get_db_connection(self.db_path) as conn:
                conn.execute("DELETE FROM conversation_history")
                conn.commit()
            return True
        except Exception as exc:
            logger.warning("Failed to clear conversation history in SQLite: %s", exc)
            return False

    def _sqlite_load(self, limit: int) -> list[dict[str, Any]] | None:
        from friday.core.database import get_db_connection

        try:
            with get_db_connection(self.db_path) as conn:
                cur = conn.execute(
                    """
                    SELECT entry_id, entry_ts, user_input, friday_reply,
                           input_type, entry_status, agents_json, metadata_json
                    FROM conversation_history
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (limit,),
                )
                cols = [d[0] for d in cur.description]
                return [dict(zip(cols, r)) for r in cur.fetchall()]
        except Exception as exc:
            logger.warning("Failed to load conversation history from SQLite: %s", exc)
            return None
