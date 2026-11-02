#!/usr/bin/env python3
"""Shared Oracle Autonomous Database helpers for the FRIDAY Universe ops scripts.

Production persistence is Oracle Autonomous Database only. Each agent owns one
unprivileged login and schema in the FRIDAY Universe DB; VyralX additionally
uses the ``VYRALX_MEDIA`` login in the VyralX media DB.

Connection strings are never stored in this repository. They are resolved, in
order, from:

1. an explicit ``--url`` / ``--env-file`` argument,
2. the process environment (``DATABASE_URL`` and the agent-prefixed variants),
3. ``/etc/friday-universe/db-credentials.env`` (both servers) and
   ``/etc/friday-universe/db-credentials-media.env`` (server 2 only).

Accepted URL shapes::

    oracle+oracledb://USER:PASSWORD@(description=(address=...)(connect_data=...))
    oracle+oracledb_async://USER:PASSWORD@adb.example.com:1521/?service_name=...
    oracle://USER:PASSWORD@DSN

The helper deliberately uses the ``oracledb`` driver directly so the checks work
even when SQLAlchemy is not installed.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple
from urllib.parse import unquote

#: Agent -> schema/login pair. Order matches the fleet layout used in AGENTS.md.
AGENT_SCHEMAS: Dict[str, str] = {
    "FRIDAY": "FRIDAY",
    "INFERENCE": "INFERENCE",
    "MEMORA": "MEMORA",
    "STRATEX": "STRATEX",
    "FUTURIS": "FUTURIS",
    "INTELX": "INTELX",
    "FORGE": "FORGE",
    "SENTINEL": "SENTINEL",
    "CORTEX": "CORTEX",
    "VYRALX": "VYRALX",
}

#: Login used by the VyralX media pipeline (separate ADB).
MEDIA_SCHEMA = "VYRALX_MEDIA"

DEFAULT_ENV_FILES: Tuple[str, ...] = (
    "/etc/friday-universe/db-credentials.env",
    "/etc/friday-universe/db-credentials-media.env",
)

#: Table counts verified on 2026-10-31. Used only to annotate the inventory
#: report; the script never treats these as live truth.
VERIFIED_TABLE_COUNTS: Dict[str, int] = {
    "FRIDAY": 15,
    "INFERENCE": 8,
    "MEMORA": 15,
    "STRATEX": 3,
    "FUTURIS": 12,
    "INTELX": 18,
    "FORGE": 7,
    "SENTINEL": 15,
    "CORTEX": 16,
    "VYRALX": 8,
}

_SCHEME_RE = re.compile(r"^oracle(?:\+oracledb(?:_async)?)?://", re.IGNORECASE)


class OracleConfigError(RuntimeError):
    """Raised when no usable Oracle connection string can be resolved."""


@dataclass(frozen=True)
class OracleTarget:
    """A parsed Oracle connection target."""

    agent: str
    user: str
    password: str
    dsn: str
    source: str

    def redacted(self) -> str:
        return f"{self.user}@{_short_dsn(self.dsn)} (from {self.source})"


def _short_dsn(dsn: str, limit: int = 72) -> str:
    flat = " ".join(dsn.split())
    if len(flat) <= limit:
        return flat
    return flat[: limit - 3] + "..."


def parse_oracle_url(url: str, agent: str = "?", source: str = "argument") -> OracleTarget:
    """Split an SQLAlchemy-style Oracle URL into driver-level components."""

    raw = (url or "").strip().strip('"').strip("'")
    if not raw:
        raise OracleConfigError(f"Empty Oracle URL for {agent}")
    if not _SCHEME_RE.match(raw):
        raise OracleConfigError(
            f"{agent}: expected an oracle+oracledb:// URL, got scheme "
            f"{raw.split('://', 1)[0] if '://' in raw else raw!r}"
        )

    body = _SCHEME_RE.sub("", raw, count=1)
    if "@" not in body:
        raise OracleConfigError(f"{agent}: URL has no 'USER:PASSWORD@DSN' section")

    credentials, dsn = body.rsplit("@", 1)
    if ":" in credentials:
        user, password = credentials.split(":", 1)
    else:
        user, password = credentials, ""
    user = unquote(user)
    password = unquote(password)
    if not user:
        raise OracleConfigError(f"{agent}: URL has an empty user name")
    if not dsn:
        raise OracleConfigError(f"{agent}: URL has an empty DSN")
    return OracleTarget(agent=agent, user=user, password=password, dsn=dsn, source=source)


def load_env_file(path: str | os.PathLike[str]) -> Dict[str, str]:
    """Parse a simple KEY=VALUE env file (comments, blanks and quotes tolerated)."""

    values: Dict[str, str] = {}
    file_path = Path(path)
    if not file_path.is_file():
        return values
    for line in file_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key.startswith("export "):
            key = key[len("export ") :].strip()
        values[key] = value.strip().strip('"').strip("'")
    return values


def _candidate_keys(agent: str, media: bool = False) -> Iterable[str]:
    names = [agent]
    if media:
        names.insert(0, MEDIA_SCHEMA)
    for name in names:
        for suffix in ("_DATABASE_URL", "_DB_URL", "_ORACLE_URL", "_URL"):
            yield f"{name}{suffix}"
    if not media:
        yield "DATABASE_URL"
        yield "ORACLE_CORE_URL"


def resolve_target(
    agent: str,
    url: Optional[str] = None,
    env_file: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
    media: bool = False,
) -> OracleTarget:
    """Resolve a connection target for ``agent`` or raise :class:`OracleConfigError`."""

    agent = agent.upper()
    if media:
        agent = MEDIA_SCHEMA

    if url:
        return parse_oracle_url(url, agent=agent, source="--url")

    environ = dict(os.environ if env is None else env)

    files: List[str] = []
    if env_file:
        files.append(env_file)
    else:
        files.extend(DEFAULT_ENV_FILES)

    merged: Dict[str, str] = {}
    for candidate in files:
        for key, value in load_env_file(candidate).items():
            merged.setdefault(key, value)

    for key in _candidate_keys(agent, media=media):
        if environ.get(key):
            return parse_oracle_url(environ[key], agent=agent, source=f"env:{key}")
        if merged.get(key):
            return parse_oracle_url(merged[key], agent=agent, source=f"{key} in env file")

    # Fall back to discrete DSN/user/password triplets.
    user = environ.get(f"{agent}_DB_USER") or merged.get(f"{agent}_DB_USER")
    password = environ.get(f"{agent}_DB_PASSWORD") or merged.get(f"{agent}_DB_PASSWORD")
    dsn = environ.get(f"{agent}_DB_DSN") or merged.get(f"{agent}_DB_DSN")
    if user and password and dsn:
        return OracleTarget(
            agent=agent,
            user=user,
            password=password,
            dsn=dsn,
            source=f"{agent}_DB_{{USER,PASSWORD,DSN}}",
        )

    raise OracleConfigError(
        f"{agent}: no Oracle credentials found. Set {agent}_DATABASE_URL or add it to "
        f"{DEFAULT_ENV_FILES[0]}, then re-run."
    )


def connect(target: OracleTarget, timeout: int = 15):
    """Open an ``oracledb`` connection for ``target``.

    Raises :class:`OracleConfigError` with an actionable message when the driver
    is missing, so the ops scripts fail cleanly instead of dumping a traceback.
    """

    try:
        import oracledb  # type: ignore
    except ImportError as exc:  # pragma: no cover - depends on host packages
        raise OracleConfigError(
            "Python package 'oracledb' is not installed. "
            "Install it with: pip install oracledb"
        ) from exc

    try:
        return oracledb.connect(
            user=target.user,
            password=target.password,
            dsn=target.dsn,
            tcp_connect_timeout=timeout,
        )
    except Exception as exc:  # pragma: no cover - live network path
        raise OracleConfigError(f"{target.agent}: connection failed: {exc}") from exc


def current_schema(conn) -> str:
    """Return the schema Oracle resolves for the current session."""

    with conn.cursor() as cur:
        cur.execute("SELECT SYS_CONTEXT('USERENV', 'CURRENT_SCHEMA') FROM dual")
        row = cur.fetchone()
    return str(row[0]) if row else ""


def current_user(conn) -> str:
    with conn.cursor() as cur:
        cur.execute("SELECT USER FROM dual")
        row = cur.fetchone()
    return str(row[0]) if row else ""


def list_tables(conn, schema: Optional[str] = None) -> List[str]:
    """List tables visible in ``schema`` (default: the session schema)."""

    schema = (schema or current_schema(conn)).upper()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT table_name FROM all_tables WHERE owner = :owner ORDER BY table_name",
            owner=schema,
        )
        return [str(row[0]) for row in cur.fetchall()]


def table_columns(conn, schema: Optional[str] = None) -> Dict[str, int]:
    """Map table name -> column count for ``schema``."""

    schema = (schema or current_schema(conn)).upper()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT table_name, COUNT(*) FROM all_tab_columns "
            "WHERE owner = :owner GROUP BY table_name ORDER BY table_name",
            owner=schema,
        )
        return {str(row[0]): int(row[1]) for row in cur.fetchall()}


def list_schemas(conn) -> List[str]:
    """Schemas visible to the current login (excludes Oracle-maintained ones)."""

    with conn.cursor() as cur:
        cur.execute(
            "SELECT username FROM all_users "
            "WHERE oracle_maintained = 'N' ORDER BY username"
        )
        return [str(row[0]) for row in cur.fetchall()]


def describe_target(target: OracleTarget) -> str:
    """One-line, password-free description for logs."""

    return target.redacted()
