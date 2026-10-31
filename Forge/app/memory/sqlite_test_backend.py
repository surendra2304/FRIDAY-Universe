"""Explicitly opt-in SQLite backend used by the test suite only.

Production code never imports this module: :class:`app.memory.db.DatabaseManager`
is Oracle-only and resolves its DSN from ``DATABASE_URL`` / ``FORGE_DATABASE_URL``.
The test suite needs a fast, disposable relational store that can execute the
same ``StateStore`` SQL without a live Autonomous Database, so this module
provides a small adapter with the same surface.

There is deliberately no default path and no environment-variable switch: a
caller must pass an explicit ``db_path`` (always a temporary directory in the
tests), so no runtime configuration can ever activate a SQLite file.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator, Mapping, Sequence
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import aiosqlite

from app.memory.db import DbRow

# Mirrors app.memory.db.SCHEMA_TABLES with SQLite types. Kept in this test-only
# module so the production schema stays Oracle-only.
TEST_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    workspace_path TEXT NOT NULL,
    config TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    goal TEXT NOT NULL,
    requirements TEXT NOT NULL DEFAULT '[]',
    run_mode TEXT NOT NULL DEFAULT 'autonomous',
    workspace_path TEXT NOT NULL,
    max_budget REAL NOT NULL DEFAULT 10.0,
    budget_consumed REAL NOT NULL DEFAULT 0.0,
    state TEXT NOT NULL DEFAULT 'PENDING',
    progress_percentage INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,
    metadata TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_events (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    payload TEXT NOT NULL DEFAULT '{}',
    timestamp TEXT NOT NULL,
    FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS artifacts (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    name TEXT NOT NULL,
    path TEXT NOT NULL,
    file_type TEXT NOT NULL DEFAULT 'text/plain',
    size_bytes INTEGER NOT NULL DEFAULT 0,
    checksum TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS task_graphs (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    goal TEXT NOT NULL,
    nodes TEXT NOT NULL DEFAULT '{}',
    edges TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL DEFAULT 'PENDING',
    current_node_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS checkpoints (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    task_id TEXT,
    step_number INTEGER NOT NULL DEFAULT 0,
    state_data TEXT NOT NULL DEFAULT '{}',
    checksum TEXT,
    timestamp TEXT NOT NULL,
    description TEXT
);

CREATE TABLE IF NOT EXISTS memora_outbox (
    id TEXT PRIMARY KEY,
    agent_name TEXT NOT NULL,
    memory_type TEXT NOT NULL,
    content_text TEXT NOT NULL,
    source TEXT,
    confidence REAL DEFAULT 1.0,
    importance REAL DEFAULT 0.5,
    lifecycle_state TEXT DEFAULT 'active',
    tenant_id TEXT DEFAULT 'default',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_tasks_state ON tasks(state);
CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON tasks(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_tasks_updated_at ON tasks(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_events_task ON audit_events(task_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_artifacts_task ON artifacts(task_id);
CREATE INDEX IF NOT EXISTS idx_task_graphs_project ON task_graphs(project_id);
CREATE INDEX IF NOT EXISTS idx_checkpoints_project ON checkpoints(project_id);
CREATE INDEX IF NOT EXISTS idx_checkpoints_step ON checkpoints(project_id, step_number);
"""


class SQLiteTestCursor:
    """Cursor adapter returning :class:`DbRow` objects."""

    def __init__(self, cursor: aiosqlite.Cursor):
        self._cursor = cursor

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._cursor.close()

    async def fetchone(self) -> DbRow | None:
        row = await self._cursor.fetchone()
        return DbRow(dict(row)) if row is not None else None

    async def fetchall(self) -> list[DbRow]:
        rows = await self._cursor.fetchall()
        return [DbRow(dict(row)) for row in rows]


class SQLiteTestConnection:
    """Thin adapter with the same ``execute`` surface as the Oracle wrapper."""

    def __init__(self, conn: aiosqlite.Connection):
        self._conn = conn
        self.row_factory = aiosqlite.Row

    async def execute(
        self,
        query: str,
        params: Mapping[str, Any] | Sequence[Any] | None = None,
        clob_params: Sequence[str] = (),
    ) -> SQLiteTestCursor:
        # ``clob_params`` is accepted for signature parity; SQLite has no CLOBs.
        del clob_params
        if params is None:
            params = {}
        elif isinstance(params, (tuple, list)):
            params = tuple(params)
        elif not isinstance(params, Mapping):
            raise TypeError(f"Unsupported parameter type: {type(params).__name__}")
        cursor = await self._conn.execute(query, params)
        return SQLiteTestCursor(cursor)

    async def executescript(self, script: str) -> None:
        await self._conn.executescript(script)

    async def commit(self) -> None:
        await self._conn.commit()

    async def rollback(self) -> None:
        await self._conn.rollback()


class SQLiteTestDatabase:
    """Test-only database manager backed by an explicit SQLite file path."""

    def __init__(self, db_path: Path | str):
        if db_path is None or str(db_path) == "":
            raise ValueError(
                "SQLiteTestDatabase requires an explicit db_path; it is a test-only "
                "backend and must never be selected from runtime configuration."
            )
        self.db_path = Path(db_path)

    # --- Dialect surface (mirrors DatabaseManager) ---------------------------

    @property
    def configured_dialect(self) -> str:
        return "sqlite"

    @property
    def is_oracle(self) -> bool:
        return False

    @property
    def is_postgres(self) -> bool:
        return False

    @property
    def is_sqlite(self) -> bool:
        return True

    @property
    def dialect_name(self) -> str:
        return "sqlite"

    @property
    def ping_sql(self) -> str:
        return "SELECT 1"

    def row_limit_clause(self) -> str:
        return "LIMIT :row_limit"

    def get_effective_url(self) -> str:
        return f"sqlite+aiosqlite:///{self.db_path}"

    # --- Lifecycle -----------------------------------------------------------

    async def _ensure_schema(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(str(self.db_path)) as conn:
            await conn.executescript(TEST_SCHEMA_SQL)
            await conn.commit()

    @asynccontextmanager
    async def connection(self) -> AsyncGenerator[SQLiteTestConnection, None]:
        await self._ensure_schema()
        async with aiosqlite.connect(str(self.db_path), timeout=10.0) as conn:
            conn.row_factory = aiosqlite.Row
            await conn.execute("PRAGMA foreign_keys = ON;")
            yield SQLiteTestConnection(conn)

    async def init_db(self) -> None:
        await self._ensure_schema()


__all__ = ["SQLiteTestDatabase"]
