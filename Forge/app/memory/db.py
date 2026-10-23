"""
Database layer for FORGE supporting PostgreSQL (via SQLAlchemy 2.0 / asyncpg)
and SQLite (via aiosqlite).
Persists tasks, task_graphs, checkpoints, artifacts, audit_events, and projects
directly into forge_db.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Mapping
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import aiosqlite
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger("memory.db")

SCHEMA_SQL = """
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
    mode TEXT NOT NULL DEFAULT 'autonomous',
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

CREATE INDEX IF NOT EXISTS idx_tasks_state ON tasks(state);
CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON tasks(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_tasks_updated_at ON tasks(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_events_task ON audit_events(task_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_artifacts_task ON artifacts(task_id);
CREATE INDEX IF NOT EXISTS idx_task_graphs_project ON task_graphs(project_id);
CREATE INDEX IF NOT EXISTS idx_checkpoints_project ON checkpoints(project_id);
CREATE INDEX IF NOT EXISTS idx_checkpoints_step ON checkpoints(project_id, step_number);
"""


class DbRow(Mapping):
    """Dictionary-like row wrapper matching aiosqlite.Row interface."""

    def __init__(self, data: dict[str, Any]):
        self._data = dict(data)

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def __iter__(self):
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def keys(self):
        return self._data.keys()

    def values(self):
        return self._data.values()

    def items(self):
        return self._data.items()

    def __contains__(self, key: object) -> bool:
        return key in self._data

    def __repr__(self) -> str:
        return f"<DbRow {self._data}>"


class AsyncCursorWrapper:
    """Cursor wrapper for SQLAlchemy 2.0 AsyncConnection executions."""

    def __init__(self, result: Any):
        self._result = result

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    async def fetchone(self) -> DbRow | None:
        if self._result is None:
            return None
        row = self._result.mappings().first()
        return DbRow(dict(row)) if row is not None else None

    async def fetchall(self) -> list[DbRow]:
        if self._result is None:
            return []
        rows = self._result.mappings().all()
        return [DbRow(dict(r)) for r in rows]


class AsyncDbConnectionWrapper:
    """Connection wrapper abstracting SQLAlchemy AsyncConnection."""

    def __init__(self, async_conn: AsyncConnection):
        self._conn = async_conn
        self.row_factory = None

    async def execute(
        self, query: str, params: tuple | list | dict | None = None
    ) -> AsyncCursorWrapper:
        # Ignore SQLite PRAGMAs on PostgreSQL
        if query.strip().upper().startswith("PRAGMA"):
            return AsyncCursorWrapper(None)

        param_dict: dict[str, Any] = {}
        processed_query = query

        if params:
            if isinstance(params, (tuple, list)):
                parts = query.split("?")
                new_parts = []
                for idx, part in enumerate(parts[:-1]):
                    pname = f"p{idx}"
                    param_dict[pname] = params[idx]
                    new_parts.append(f"{part}:{pname}")
                new_parts.append(parts[-1])
                processed_query = "".join(new_parts)
            elif isinstance(params, dict):
                param_dict = params

        result = await self._conn.execute(text(processed_query), param_dict)
        return AsyncCursorWrapper(result)

    async def executescript(self, script: str) -> None:
        for stmt in script.split(";"):
            cleaned = stmt.strip()
            if cleaned and not cleaned.upper().startswith("PRAGMA"):
                await self._conn.execute(text(cleaned))

    async def commit(self) -> None:
        await self._conn.commit()

    async def rollback(self) -> None:
        await self._conn.rollback()


class DatabaseManager:
    """Manages PostgreSQL (via asyncpg/SQLAlchemy 2.0) and SQLite connections."""

    def __init__(
        self,
        db_path: Path | None = None,
        database_url: str | None = None,
    ):
        self.settings = get_settings()
        if db_path:
            self.db_path = db_path
        elif Path("/dev/shm").exists():
            self.db_path = Path("/dev/shm/forge.db")
        else:
            self.db_path = self.settings.base_dir / self.settings.database_path
        self._custom_url = database_url
        self._schema_ready = False
        self._schema_lock = asyncio.Lock()
        self._async_engine: AsyncEngine | None = None
        self._is_postgres: bool = False
        self._tried_postgres: bool = False

    def get_effective_url(self) -> str:
        """Return target database connection URL."""
        if self._custom_url:
            return self._custom_url
        return self.settings.get_database_url()

    async def _init_postgres_engine(self) -> AsyncEngine | None:
        """Attempt to initialize PostgreSQL async engine."""
        if self._tried_postgres:
            return self._async_engine

        self._tried_postgres = True
        url = self.get_effective_url()

        if "postgresql" in url or "oracle" in url:
            try:
                if url.startswith("oracle+oracledb://"):
                    url = "oracle+oracledb_async://" + url[len("oracle+oracledb://"):]
                engine = create_async_engine(
                    url,
                    pool_pre_ping=True,
                    pool_size=10,
                    max_overflow=20,
                    connect_args={"timeout": 4} if "postgresql" in url else {},
                )
                # Quick test connection
                async with engine.connect() as conn:
                    await conn.execute(text("SELECT 1 FROM DUAL" if "oracle" in url else "SELECT 1"))
                self._async_engine = engine
                self._is_postgres = True
                logger.info(f"Connected to relational database (PostgreSQL/Oracle) at: {url.split('@')[-1]}")
                return self._async_engine
            except Exception as e:
                logger.warning(
                    f"PostgreSQL unreachable at {url} ({type(e).__name__}: {e}). "
                    f"Falling back to high-performance SQLite store."
                )
                self._is_postgres = False
                self._async_engine = None
        return None

    async def _ensure_schema(self) -> None:
        """Create tables and indexes idempotently on PostgreSQL or SQLite."""
        if self._schema_ready:
            return
        async with self._schema_lock:
            if self._schema_ready:
                return

            engine = await self._init_postgres_engine()
            if engine is not None and self._is_postgres:
                try:
                    async with engine.begin() as conn:
                        for stmt in SCHEMA_SQL.split(";"):
                            cleaned = stmt.strip()
                            if cleaned and not cleaned.upper().startswith("PRAGMA"):
                                try:
                                    await conn.execute(text(cleaned))
                                except Exception:
                                    pass
                    self._schema_ready = True
                    return
                except Exception as e:
                    logger.warning(f"Error ensuring PostgreSQL schema: {e}. Falling back to SQLite.")
                    self._is_postgres = False

            # SQLite schema initialization
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            async with aiosqlite.connect(str(self.db_path)) as conn:
                await conn.executescript(SCHEMA_SQL)
                try:
                    await conn.execute(
                        "ALTER TABLE tasks ADD COLUMN metadata TEXT NOT NULL DEFAULT '{}';"
                    )
                except Exception:
                    pass
                await conn.commit()
            self._schema_ready = True

    @asynccontextmanager
    async def connection(self) -> AsyncGenerator[Any, None]:
        """Async context manager yielding a database connection (PostgreSQL or SQLite)."""
        await self._ensure_schema()

        if self._is_postgres and self._async_engine is not None:
            try:
                async with self._async_engine.connect() as conn:
                    trans = await conn.begin()
                    wrapper = AsyncDbConnectionWrapper(conn)
                    try:
                        yield wrapper
                        if trans.is_active:
                            await trans.commit()
                    except Exception:
                        if trans.is_active:
                            await trans.rollback()
                        raise
                return
            except Exception as e:
                logger.warning(f"PostgreSQL connection error: {e}. Falling back to SQLite.")

        # SQLite fallback connection
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(str(self.db_path), timeout=10.0) as conn:
            conn.row_factory = aiosqlite.Row
            await conn.execute("PRAGMA journal_mode = WAL;")
            await conn.execute("PRAGMA synchronous = NORMAL;")
            await conn.execute("PRAGMA busy_timeout = 5000;")
            await conn.execute("PRAGMA foreign_keys = ON;")
            yield conn

    async def init_db(self) -> None:
        """Initialize database tables and indexes (idempotent)."""
        await self._ensure_schema()
        target = "PostgreSQL" if self._is_postgres else f"SQLite ({self.db_path})"
        logger.info(f"Initialized FORGE database using {target}")


# Global singleton instance
db_manager = DatabaseManager()


async def get_db() -> AsyncGenerator[Any, None]:
    """FastAPI dependency for yielding database connections."""
    async with db_manager.connection() as conn:
        yield conn
