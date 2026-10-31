"""
Oracle Autonomous Database persistence layer for FORGE.

The only supported backend is Oracle Autonomous Database, reached through
SQLAlchemy 2.0's ``oracle+oracledb`` (python-oracledb) async dialect. There is
no SQLite file and no PostgreSQL driver anywhere on the runtime path: an
unset or non-Oracle ``DATABASE_URL`` raises :class:`RuntimeError` during
startup instead of silently creating a local database.

Oracle differences handled here:

* ``LIMIT`` does not exist -- ``FETCH FIRST :row_limit ROWS ONLY`` is used.
* ``''`` is stored as ``NULL``.
* Scalar selects need ``FROM DUAL``.
* Upserts use ``MERGE``.
* Schema discovery uses ``user_tables`` / ``user_indexes`` rather than
  ``CREATE TABLE IF NOT EXISTS`` (not portable across ADB versions).
* CLOB columns come back as LOB objects and must be read with ``.read()``.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Mapping, Sequence
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy import CLOB, bindparam, text
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


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

SCHEMA_TABLES: dict[str, str] = {
    "projects": """
CREATE TABLE projects (
    id VARCHAR2(64) PRIMARY KEY,
    name VARCHAR2(255) NOT NULL,
    description CLOB,
    workspace_path VARCHAR2(1024) NOT NULL,
    config CLOB DEFAULT '{}',
    created_at VARCHAR2(64) NOT NULL,
    updated_at VARCHAR2(64) NOT NULL
)""",
    "tasks": """
CREATE TABLE tasks (
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
)""",
    "audit_events": """
CREATE TABLE audit_events (
    id VARCHAR2(64) PRIMARY KEY,
    task_id VARCHAR2(64) NOT NULL,
    event_type VARCHAR2(64) NOT NULL,
    payload CLOB DEFAULT '{}',
    timestamp VARCHAR2(64) NOT NULL,
    CONSTRAINT fk_audit_events_task FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE
)""",
    "artifacts": """
CREATE TABLE artifacts (
    id VARCHAR2(64) PRIMARY KEY,
    task_id VARCHAR2(64) NOT NULL,
    name VARCHAR2(255) NOT NULL,
    path VARCHAR2(1024) NOT NULL,
    file_type VARCHAR2(128) DEFAULT 'text/plain',
    size_bytes NUMBER(12) DEFAULT 0,
    checksum VARCHAR2(128),
    created_at VARCHAR2(64) NOT NULL,
    CONSTRAINT fk_artifacts_task FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE
)""",
    "task_graphs": """
CREATE TABLE task_graphs (
    id VARCHAR2(64) PRIMARY KEY,
    project_id VARCHAR2(64) NOT NULL,
    goal CLOB NOT NULL,
    nodes CLOB DEFAULT '{}',
    edges CLOB DEFAULT '[]',
    status VARCHAR2(32) DEFAULT 'PENDING',
    current_node_id VARCHAR2(64),
    created_at VARCHAR2(64) NOT NULL,
    updated_at VARCHAR2(64) NOT NULL
)""",
    "checkpoints": """
CREATE TABLE checkpoints (
    id VARCHAR2(64) PRIMARY KEY,
    project_id VARCHAR2(64) NOT NULL,
    task_id VARCHAR2(64),
    step_number NUMBER(10) DEFAULT 0,
    state_data CLOB DEFAULT '{}',
    checksum VARCHAR2(128),
    timestamp VARCHAR2(64) NOT NULL,
    description CLOB
)""",
    "memora_outbox": """
CREATE TABLE memora_outbox (
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
)""",
}

SCHEMA_INDEXES: dict[str, str] = {
    "idx_tasks_state": "CREATE INDEX idx_tasks_state ON tasks(state)",
    "idx_tasks_created_at": "CREATE INDEX idx_tasks_created_at ON tasks(created_at DESC)",
    "idx_tasks_updated_at": "CREATE INDEX idx_tasks_updated_at ON tasks(updated_at DESC)",
    "idx_audit_events_task": "CREATE INDEX idx_audit_events_task ON audit_events(task_id, timestamp)",
    "idx_artifacts_task": "CREATE INDEX idx_artifacts_task ON artifacts(task_id)",
    "idx_task_graphs_project": "CREATE INDEX idx_task_graphs_project ON task_graphs(project_id)",
    "idx_checkpoints_project": "CREATE INDEX idx_checkpoints_project ON checkpoints(project_id)",
    "idx_checkpoints_step": "CREATE INDEX idx_checkpoints_step ON checkpoints(project_id, step_number)",
}

# Kept for callers that want the complete DDL as one string (diagnostics/tests).
SCHEMA_SQL_ORACLE = "\n\n".join(SCHEMA_TABLES.values()) + "\n\n" + "\n".join(
    SCHEMA_INDEXES.values()
)

# Reused by `app.integrations.memora_outbox` when it creates the table lazily,
# before DatabaseManager.init_db() has run.
MEMORA_OUTBOX_DDL_ORACLE = SCHEMA_TABLES["memora_outbox"]


# "Object already exists" is the only class of DDL failure that is safe to
# ignore: `_ensure_schema` is explicitly idempotent. Every other failure is
# surfaced, because a partially created schema silently degrades the whole
# persistence layer (this is how the `MODE` column rename went unnoticed).
_ORACLE_BENIGN_DDL_CODES = (
    "ORA-00955",  # name is already used by an existing object
    "ORA-01408",  # such column list already indexed
    "ORA-02275",  # such referential constraint already exists
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
    return "ALREADY EXISTS" in blob


def ping_statement(db: Any) -> str:
    """Return the dialect-correct scalar ping for *db*.

    ``getattr`` keeps duck-typed/test doubles (which only implement
    ``connection()``) working, while a real ``DatabaseManager`` answers
    ``SELECT 1 FROM DUAL`` on Oracle.
    """
    return getattr(db, "ping_sql", "SELECT 1")


class DbRow(Mapping):
    """Dictionary-like row wrapper used by every caller.

    Keys are normalised to lower case because Oracle returns unquoted column
    names in upper case. Callers index rows by their lower-case column names.
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
    """Connection wrapper over a SQLAlchemy ``AsyncConnection``.

    Only named ``:bind`` parameters are accepted. Positional ``?`` binds are
    rejected loudly because Oracle does not support them and silently rewriting
    them was the source of dialect drift.
    """

    def __init__(self, async_conn: AsyncConnection, dialect: str = "oracle"):
        self._conn = async_conn
        self._dialect = dialect
        self.row_factory = None

    @property
    def dialect_name(self) -> str:
        return self._dialect

    @staticmethod
    def _coerce(value: Any) -> Any:
        # Oracle has no BOOLEAN column type; legacy NUMBER(1) flags must
        # receive 0/1 rather than a Python bool.
        return int(value) if isinstance(value, bool) else value

    async def execute(
        self,
        query: str,
        params: Mapping[str, Any] | Sequence[Any] | None = None,
        clob_params: Sequence[str] = (),
    ) -> AsyncCursorWrapper:
        if params is None:
            param_dict: dict[str, Any] = {}
        elif isinstance(params, Mapping):
            param_dict = {str(k): self._coerce(v) for k, v in params.items()}
        elif isinstance(params, (tuple, list)):
            if params:
                raise TypeError(
                    "Oracle backend requires named :bind parameters; positional "
                    f"'?' binds are not supported (query: {query[:120]!r})."
                )
            param_dict = {}
        else:
            raise TypeError(
                "Database parameters must be a mapping of named :bind values, "
                f"got {type(params).__name__}."
            )

        stmt = text(query)
        if clob_params:
            stmt = stmt.bindparams(*(bindparam(name, type_=CLOB) for name in clob_params))
        result = await self._conn.execute(stmt, param_dict)
        return AsyncCursorWrapper(result)

    async def executescript(self, script: str) -> None:
        for stmt in script.split(";"):
            cleaned = stmt.strip()
            if cleaned:
                await self._conn.execute(text(cleaned))

    async def commit(self) -> None:
        await self._conn.commit()

    async def rollback(self) -> None:
        await self._conn.rollback()


class DatabaseManager:
    """Manages the Oracle Autonomous Database connection pool.

    The manager is intentionally Oracle-only. Constructing it does not open a
    connection; the DSN is resolved and validated on first use so that a
    missing/malformed URL fails at startup (``init_db``) rather than on the
    first request.
    """

    def __init__(self, database_url: str | None = None):
        self.settings = get_settings()
        self._custom_url = database_url
        self._schema_ready = False
        self._schema_lock = asyncio.Lock()
        self._async_engine: AsyncEngine | None = None

    # --- Dialect introspection ------------------------------------------------

    @property
    def configured_dialect(self) -> str:
        """Dialect implied by the configured URL.

        Validates the URL, so a PostgreSQL/SQLite DSN raises instead of being
        misreported as something else.
        """
        self.get_effective_url()
        return "oracle"

    @property
    def is_oracle(self) -> bool:
        """True: Oracle Autonomous Database is the only supported backend."""
        return True

    @property
    def is_postgres(self) -> bool:
        """Always False; retained for callers that ask."""
        return False

    @property
    def is_sqlite(self) -> bool:
        """Always False; retained for callers that ask."""
        return False

    @property
    def dialect_name(self) -> str:
        """Active SQL dialect."""
        return "oracle"

    @property
    def ping_sql(self) -> str:
        """Scalar ``SELECT`` usable on Oracle."""
        return "SELECT 1 FROM DUAL"

    def row_limit_clause(self) -> str:
        """Oracle row limit, appended after ``ORDER BY``.

        The limit itself is bound as ``:row_limit`` so callers build one
        parameter mapping.
        """
        return "FETCH FIRST :row_limit ROWS ONLY"

    def get_effective_url(self) -> str:
        """Return the validated Oracle connection URL."""
        if self._custom_url:
            url = self._custom_url.strip()
            if not url.lower().startswith(
                ("oracle+oracledb://", "oracle+oracledb_async://")
            ):
                raise RuntimeError(
                    "Unsupported database URL for FORGE. Oracle Autonomous Database is "
                    "the only supported backend; expected an oracle+oracledb:// DSN."
                )
            return url
        return self.settings.get_database_url()

    # --- Engine / schema ------------------------------------------------------

    def _get_engine(self) -> AsyncEngine:
        """Create (once) the async Oracle engine."""
        if self._async_engine is None:
            url = self.get_effective_url()
            self._async_engine = create_async_engine(
                url,
                pool_pre_ping=True,
                pool_size=10,
                max_overflow=20,
                pool_recycle=1800,
            )
            # Log only the connect descriptor, never the credentials.
            logger.info(
                "Configured Oracle Autonomous Database engine at: %s",
                url.split("@")[-1],
            )
        return self._async_engine

    @staticmethod
    async def _object_exists(conn: AsyncConnection, view: str, column: str, name: str) -> bool:
        result = await conn.execute(
            text(f"SELECT COUNT(*) FROM {view} WHERE {column} = :object_name"),
            {"object_name": name.upper()},
        )
        return int(result.scalar_one()) > 0

    async def _ensure_schema(self) -> None:
        """Create missing tables/indexes idempotently using ``user_tables``."""
        if self._schema_ready:
            return
        async with self._schema_lock:
            if self._schema_ready:
                return

            engine = self._get_engine()
            failures: list[tuple[str, Exception]] = []
            async with engine.begin() as conn:
                for table, ddl in SCHEMA_TABLES.items():
                    if await self._object_exists(conn, "user_tables", "table_name", table):
                        continue
                    try:
                        await conn.execute(text(ddl))
                        logger.debug("Created Oracle table %s", table.upper())
                    except Exception as exc:
                        head = " ".join(ddl.split())[:120]
                        if is_benign_ddl_error(exc):
                            logger.debug("Oracle DDL already applied [%s]", head)
                            continue
                        logger.error(
                            "Oracle DDL failed [%s]: %s: %s",
                            head,
                            type(exc).__name__,
                            exc,
                        )
                        failures.append((head, exc))

                for index, ddl in SCHEMA_INDEXES.items():
                    if await self._object_exists(conn, "user_indexes", "index_name", index):
                        continue
                    try:
                        await conn.execute(text(ddl))
                    except Exception as exc:
                        head = " ".join(ddl.split())[:120]
                        if is_benign_ddl_error(exc):
                            continue
                        logger.error(
                            "Oracle index DDL failed [%s]: %s: %s",
                            head,
                            type(exc).__name__,
                            exc,
                        )
                        failures.append((head, exc))

            if failures:
                head, exc = failures[0]
                raise RuntimeError(
                    f"Oracle schema initialisation incomplete: {len(failures)} DDL "
                    f"statement(s) failed. First failure [{head}]: {exc}"
                ) from exc
            self._schema_ready = True

    @asynccontextmanager
    async def connection(self) -> AsyncGenerator[Any, None]:
        """Yield a transactional Oracle connection.

        Connection or SQL failures propagate: there is no fallback engine to
        replay the statement against.
        """
        await self._ensure_schema()
        engine = self._get_engine()
        conn = await engine.connect()
        trans = await conn.begin()
        try:
            yield AsyncDbConnectionWrapper(conn, dialect="oracle")
            if trans.is_active:
                await trans.commit()
        except BaseException:
            if trans.is_active:
                await trans.rollback()
            raise
        finally:
            await conn.close()

    async def init_db(self) -> None:
        """Initialize database tables and indexes (idempotent)."""
        await self._ensure_schema()
        logger.info("Initialized FORGE database using Oracle Autonomous Database 23ai")


# Global singleton instance
db_manager = DatabaseManager()


async def get_db() -> AsyncGenerator[Any, None]:
    """FastAPI dependency for yielding database connections."""
    async with db_manager.connection() as conn:
        yield conn
