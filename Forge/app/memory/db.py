"""
Database layer for FORGE supporting Oracle Autonomous Database 23ai (via
SQLAlchemy 2.0 / python-oracledb), PostgreSQL (via SQLAlchemy 2.0 / asyncpg)
and SQLite (via aiosqlite).
Persists tasks, task_graphs, checkpoints, artifacts, audit_events, projects and
the Memora outbox directly into the active relational database.

Dialect differences are confined to this module and `StateStore`: Oracle has no
``LIMIT`` clause (``FETCH FIRST n ROWS ONLY``), treats ``''`` as ``NULL``, has no
``ON CONFLICT`` upsert, and requires ``FROM DUAL`` for scalar selects.
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
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.types import JSON

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger("memory.db")


@compiles(JSON, "oracle")
def _compile_json_oracle(_type, _compiler, **_kw):
    """Oracle 23ai natively supports the JSON data type."""
    return "JSON"


SCHEMA_SQL_ORACLE = """
CREATE TABLE IF NOT EXISTS projects (
    id VARCHAR2(64) PRIMARY KEY,
    name VARCHAR2(255) NOT NULL,
    description CLOB,
    workspace_path VARCHAR2(1024) NOT NULL,
    config CLOB DEFAULT '{}',
    created_at VARCHAR2(64) NOT NULL,
    updated_at VARCHAR2(64) NOT NULL
);

CREATE TABLE IF NOT EXISTS tasks (
    id VARCHAR2(64) PRIMARY KEY,
    goal CLOB NOT NULL,
    requirements CLOB DEFAULT '[]',
    run_mode VARCHAR2(32) DEFAULT 'autonomous',
    workspace_path VARCHAR2(1024) NOT NULL,
    max_budget NUMBER(10,2) DEFAULT 10.0,
    budget_consumed NUMBER(10,2) DEFAULT 0.0,
    state VARCHAR2(32) DEFAULT 'PENDING',
    progress_percentage NUMBER(5) DEFAULT 0,
    error_message CLOB,
    metadata CLOB DEFAULT '{}',
    created_at VARCHAR2(64) NOT NULL,
    updated_at VARCHAR2(64) NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_events (
    id VARCHAR2(64) PRIMARY KEY,
    task_id VARCHAR2(64) NOT NULL,
    event_type VARCHAR2(64) NOT NULL,
    payload CLOB DEFAULT '{}',
    timestamp VARCHAR2(64) NOT NULL,
    CONSTRAINT fk_audit_events_task FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS artifacts (
    id VARCHAR2(64) PRIMARY KEY,
    task_id VARCHAR2(64) NOT NULL,
    name VARCHAR2(255) NOT NULL,
    path VARCHAR2(1024) NOT NULL,
    file_type VARCHAR2(128) DEFAULT 'text/plain',
    size_bytes NUMBER(12) DEFAULT 0,
    checksum VARCHAR2(128),
    created_at VARCHAR2(64) NOT NULL,
    CONSTRAINT fk_artifacts_task FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS task_graphs (
    id VARCHAR2(64) PRIMARY KEY,
    project_id VARCHAR2(64) NOT NULL,
    goal CLOB NOT NULL,
    nodes CLOB DEFAULT '{}',
    edges CLOB DEFAULT '[]',
    status VARCHAR2(32) DEFAULT 'PENDING',
    current_node_id VARCHAR2(64),
    created_at VARCHAR2(64) NOT NULL,
    updated_at VARCHAR2(64) NOT NULL
);

CREATE TABLE IF NOT EXISTS checkpoints (
    id VARCHAR2(64) PRIMARY KEY,
    project_id VARCHAR2(64) NOT NULL,
    task_id VARCHAR2(64),
    step_number NUMBER(10) DEFAULT 0,
    state_data CLOB DEFAULT '{}',
    checksum VARCHAR2(128),
    timestamp VARCHAR2(64) NOT NULL,
    description CLOB
);

CREATE TABLE IF NOT EXISTS memora_outbox (
    id VARCHAR2(64) PRIMARY KEY,
    agent_name VARCHAR2(128) NOT NULL,
    memory_type VARCHAR2(64) NOT NULL,
    content_text CLOB NOT NULL,
    source VARCHAR2(1024),
    confidence NUMBER(6,4) DEFAULT 1.0,
    importance NUMBER(6,4) DEFAULT 0.5,
    lifecycle_state VARCHAR2(32) DEFAULT 'active',
    tenant_id VARCHAR2(64) DEFAULT 'default',
    created_at VARCHAR2(64) NOT NULL
);
"""

# Reused by `app.integrations.memora_outbox` when it creates the table lazily,
# before DatabaseManager.init_db() has run.
MEMORA_OUTBOX_DDL_ORACLE = """
CREATE TABLE IF NOT EXISTS memora_outbox (
    id VARCHAR2(64) PRIMARY KEY,
    agent_name VARCHAR2(128) NOT NULL,
    memory_type VARCHAR2(64) NOT NULL,
    content_text CLOB NOT NULL,
    source VARCHAR2(1024),
    confidence NUMBER(6,4) DEFAULT 1.0,
    importance NUMBER(6,4) DEFAULT 0.5,
    lifecycle_state VARCHAR2(32) DEFAULT 'active',
    tenant_id VARCHAR2(64) DEFAULT 'default',
    created_at VARCHAR2(64) NOT NULL
)
"""

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

CREATE INDEX IF NOT EXISTS idx_tasks_state ON tasks(state);
CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON tasks(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_tasks_updated_at ON tasks(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_events_task ON audit_events(task_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_artifacts_task ON artifacts(task_id);
CREATE INDEX IF NOT EXISTS idx_task_graphs_project ON task_graphs(project_id);
CREATE INDEX IF NOT EXISTS idx_checkpoints_project ON checkpoints(project_id);
CREATE INDEX IF NOT EXISTS idx_checkpoints_step ON checkpoints(project_id, step_number);
"""


# "Object already exists" is the only class of DDL failure that is safe to
# ignore: `_ensure_schema` is explicitly idempotent. Every other failure is
# surfaced, because a partially created schema silently degrades the whole
# persistence layer (this is how the `MODE` column rename went unnoticed).
_ORACLE_BENIGN_DDL_CODES = (
    "ORA-00955",  # name is already used by an existing object
    "ORA-01408",  # such column list already indexed
    "ORA-02275",  # such referential constraint already exists
)
_POSTGRES_BENIGN_SQLSTATES = frozenset(
    {
        "42P07",  # duplicate_table
        "42710",  # duplicate_object
        "42701",  # duplicate_column
        "42P16",  # invalid_table_definition (concurrent IF NOT EXISTS race)
    }
)
_POSTGRES_BENIGN_ERROR_NAMES = frozenset(
    {"DuplicateTable", "DuplicateObject", "DuplicateColumn"}
)


def is_benign_ddl_error(exc: BaseException) -> bool:
    """Return True only for DDL errors meaning "this object already exists"."""
    orig = getattr(exc, "orig", exc)
    chunks = [str(exc), str(orig)]
    for arg in getattr(orig, "args", ()) or ():
        chunks.append(str(arg))
    blob = " | ".join(chunks).upper()

    if any(code in blob for code in _ORACLE_BENIGN_DDL_CODES):
        return True
    sqlstate = getattr(orig, "sqlstate", None) or getattr(orig, "pgcode", None)
    if sqlstate in _POSTGRES_BENIGN_SQLSTATES:
        return True
    if type(orig).__name__ in _POSTGRES_BENIGN_ERROR_NAMES:
        return True
    # SQLite raises OperationalError("table x already exists") and Oracle's
    # ORA-00955 message also contains "already ... existing object".
    return "ALREADY EXISTS" in blob


def ping_statement(db: Any) -> str:
    """Return the dialect-correct scalar ping for *db*.

    ``getattr`` keeps duck-typed/test doubles (which only implement
    ``connection()``) working, while a real ``DatabaseManager`` answers
    ``SELECT 1 FROM DUAL`` on Oracle.
    """
    return getattr(db, "ping_sql", "SELECT 1")


class DbRow(Mapping):
    """Dictionary-like row wrapper matching aiosqlite.Row interface.

    Keys are normalised to lower case because Oracle returns unquoted column
    names in upper case while SQLite and PostgreSQL return them as declared.
    Callers index rows by their lower-case column names on every backend.
    """

    def __init__(self, data: dict[str, Any]):
        self._data = {str(k).lower(): v for k, v in data.items()}

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

    def __init__(self, async_conn: AsyncConnection, dialect: str = "postgresql"):
        self._conn = async_conn
        self._dialect = dialect
        self.row_factory = None

    @property
    def dialect_name(self) -> str:
        return self._dialect

    async def execute(
        self, query: str, params: tuple | list | dict | None = None
    ) -> AsyncCursorWrapper:
        # SQLite-only PRAGMAs are meaningless on Oracle/PostgreSQL; the wrapper
        # silently ignores them so callers can stay backend-agnostic.
        if query.strip().upper().startswith("PRAGMA"):
            return AsyncCursorWrapper(None)

        param_dict: dict[str, Any] = {}
        processed_query = query

        if params:
            if isinstance(params, (tuple, list)):
                values = list(params)
                if self._dialect == "oracle":
                    # Oracle has no BOOLEAN column type; legacy NUMBER(1) flags
                    # must receive 0/1 rather than a Python bool.
                    values = [int(v) if isinstance(v, bool) else v for v in values]
                parts = query.split("?")
                new_parts = []
                for idx, part in enumerate(parts[:-1]):
                    pname = f"p{idx}"
                    param_dict[pname] = values[idx]
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
        self._is_oracle: bool = False
        self._tried_postgres: bool = False

    # --- Dialect introspection ------------------------------------------------

    @property
    def configured_dialect(self) -> str:
        """Dialect implied by the configured URL, without opening a connection."""
        url = self.get_effective_url().lower()
        if url.startswith("oracle") or "oracle+oracledb" in url:
            return "oracle"
        if url.startswith("postgresql") or "+asyncpg" in url:
            return "postgresql"
        return "sqlite"

    @property
    def is_oracle(self) -> bool:
        """True when SQL is executed against Oracle.

        Before the first connection attempt the configured URL is the only
        signal available, so it is used to answer correctly for callers that
        build SQL before opening a connection (the Oracle fallback to SQLite
        clears the flag again).
        """
        if self._is_oracle:
            return True
        if not self._tried_postgres:
            return self.configured_dialect == "oracle"
        return False

    @property
    def is_postgres(self) -> bool:
        """True when SQL is executed against PostgreSQL."""
        return self._is_postgres

    @property
    def is_sqlite(self) -> bool:
        """True when the SQLite fallback is the active backend."""
        return not (self._is_postgres or self.is_oracle)

    @property
    def dialect_name(self) -> str:
        """Active SQL dialect: ``oracle``, ``postgresql`` or ``sqlite``."""
        if self.is_oracle:
            return "oracle"
        if self._is_postgres:
            return "postgresql"
        return "sqlite"

    @property
    def ping_sql(self) -> str:
        """Scalar ``SELECT`` usable on the active backend."""
        return "SELECT 1 FROM DUAL" if self.is_oracle else "SELECT 1"

    def row_limit_clause(self) -> str:
        """Dialect-specific row limit, appended after ``ORDER BY``.

        The limit itself is always bound as the next positional parameter so
        callers keep building one parameter tuple for every backend.
        """
        if self.is_oracle:
            return "FETCH FIRST ? ROWS ONLY"
        return "LIMIT ?"

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
                if url.startswith("postgresql://"):
                    url = "postgresql+asyncpg://" + url[len("postgresql://"):]
                elif url.startswith("oracle+oracledb://"):
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
                self._is_oracle = "oracle" in url
                db_kind = "Oracle 23ai" if self._is_oracle else "PostgreSQL"
                logger.info(f"Connected to relational database ({db_kind}) at: {url.split('@')[-1]}")
                return self._async_engine
            except Exception as e:
                logger.warning(
                    f"Relational database unreachable at {url.split('@')[-1]} "
                    f"({type(e).__name__}: {e}). "
                    f"Falling back to high-performance SQLite store."
                )
                self._is_postgres = False
                self._is_oracle = False
                self._async_engine = None
        return None

    async def _ensure_schema(self) -> None:
        """Create tables and indexes idempotently on Oracle, PostgreSQL, or SQLite."""
        if self._schema_ready:
            return
        async with self._schema_lock:
            if self._schema_ready:
                return

            # Resolve the backend *before* choosing the DDL script: the previous
            # order read `_is_oracle` before `_init_postgres_engine()` had run,
            # so the first call on a fresh process always executed the SQLite
            # script against Oracle.
            engine = await self._init_postgres_engine()
            if engine is not None and self._is_postgres:
                dialect = "oracle" if self._is_oracle else "postgresql"
                schema_to_run = SCHEMA_SQL_ORACLE if self._is_oracle else SCHEMA_SQL
                failures: list[tuple[str, Exception]] = []
                try:
                    async with engine.begin() as conn:
                        for stmt in schema_to_run.split(";"):
                            cleaned = stmt.strip()
                            if not cleaned or cleaned.upper().startswith("PRAGMA"):
                                continue
                            try:
                                await conn.execute(text(cleaned))
                            except Exception as exc:
                                head = " ".join(cleaned.split())[:120]
                                if is_benign_ddl_error(exc):
                                    logger.debug(f"{dialect} DDL already applied [{head}]")
                                    continue
                                logger.error(
                                    f"{dialect} DDL failed [{head}]: "
                                    f"{type(exc).__name__}: {exc}"
                                )
                                failures.append((head, exc))
                except Exception as e:
                    # Connection/transaction level problem: keep the historical
                    # SQLite fallback, but make it loud instead of silent.
                    logger.error(
                        f"{dialect} schema initialisation could not run "
                        f"({type(e).__name__}: {e}). Falling back to SQLite store."
                    )
                    self._is_postgres = False
                    self._is_oracle = False
                    self._async_engine = None
                else:
                    if failures:
                        head, exc = failures[0]
                        raise RuntimeError(
                            f"{dialect} schema initialisation incomplete: "
                            f"{len(failures)} DDL statement(s) failed. "
                            f"First failure [{head}]: {exc}"
                        ) from exc
                    self._schema_ready = True
                    return

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
        """Async context manager yielding a database connection (relational or SQLite)."""
        await self._ensure_schema()

        if self._is_postgres and self._async_engine is not None:
            # Only a failure to *acquire* the connection may fall back to SQLite.
            # The previous structure wrapped `yield`, so any error raised by the
            # caller (including a genuine Oracle/PostgreSQL SQL error) was logged
            # as a "connection error" and the block was replayed against SQLite,
            # hiding incompatibilities instead of reporting them.
            try:
                conn = await self._async_engine.connect()
            except Exception as e:
                logger.error(
                    f"{self.dialect_name} connection error: {type(e).__name__}: {e}. "
                    f"Falling back to SQLite."
                )
                self._is_postgres = False
                self._is_oracle = False
            else:
                trans = await conn.begin()
                try:
                    yield AsyncDbConnectionWrapper(conn, dialect=self.dialect_name)
                    if trans.is_active:
                        await trans.commit()
                except Exception:
                    if trans.is_active:
                        await trans.rollback()
                    raise
                finally:
                    await conn.close()
                return

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
        if self.is_oracle:
            target = "Oracle Autonomous Database 23ai"
        elif self._is_postgres:
            target = "PostgreSQL"
        else:
            target = f"SQLite ({self.db_path})"
        logger.info(f"Initialized FORGE database using {target}")


# Global singleton instance
db_manager = DatabaseManager()


async def get_db() -> AsyncGenerator[Any, None]:
    """FastAPI dependency for yielding database connections."""
    async with db_manager.connection() as conn:
        yield conn
