"""Memora/core/memory/context_durability.py — Durable viking:// snapshot store.

TASK-MEM-010: the relational persistence point for the ``viking://`` context
database. ``core/memory/real_viking_context.py`` (stdlib-only) defines the
snapshot contract — ``state_payload`` / ``restore_state`` /
``PersistentContextDatabase`` — and calls into this module for the durable
backend. Splitting it this way keeps the context engine importable without an
ORM while the store rides the existing relational stack: the same session
factory that serves the memory records, so production writes go to Oracle
Autonomous Database and the test suite's explicitly-configured file-backed
SQLite (``tests/conftest.py`` pins ``MEMORA_ENV=testing``). There is no SQLite
fallback outside that test path — ``storage.relational.session`` enforces it.

The backend table is ``context_snapshots`` (storage/relational/models.py, one
row per ``(tenant_id, scope_key)``). Isolation follows the access_scope
conventions: every read and write filters on both key parts, an unknown pair
matches nothing (fail-closed), and a store for tenant A can never return
tenant B's payload.

Honesty rules:

* ``load`` verifies the stored sha256 before trusting a payload; a digest
  mismatch raises instead of returning half-trusted content.
* ``save`` refuses to overwrite a snapshot that this process never read
  (``_loaded`` guard). A transient backend outage at startup must not turn
  into silent data loss on the first write after recovery.
* Nothing here fabricates content: restore decisions belong to the caller
  (``PersistentContextDatabase.restore_or_empty``), which starts empty and
  logs when the store is unavailable.
"""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any

from storage.relational.base import get_utc_now
from storage.relational.models import ContextSnapshot

logger = logging.getLogger(__name__)

#: Tenant bucket for the context snapshot when the caller does not name one.
#: Matches the default every relational table in Memora uses.
DEFAULT_TENANT_ID = "default"

MAX_SCOPE_KEY_CHARS = 128


def normalize_scope_key(value: Any) -> str:
    """Validate the per-tenant context identity a snapshot is stored under.

    Mirrors ``ContextDatabase``'s user validation: a scope key must be a
    single viking path segment. Invalid keys fail closed rather than silently
    aliasing two different context users onto one row.
    """
    import re

    key = str(value or "").strip()
    if not key or len(key) > MAX_SCOPE_KEY_CHARS or not re.match(r"^[A-Za-z0-9._\-]+$", key):
        raise ValueError(f"invalid context scope key {value!r}")
    return key


class RelationalContextSnapshotStore:
    """Snapshot store over the relational (Oracle / test-SQLite) backend."""

    def __init__(self, tenant_id: str = DEFAULT_TENANT_ID, scope_key: str = "memora",
                 session_factory: Any | None = None) -> None:
        self.tenant_id = str(tenant_id or DEFAULT_TENANT_ID).strip() or DEFAULT_TENANT_ID
        self.scope_key = normalize_scope_key(scope_key)
        self._session_factory = session_factory
        #: True only once the current snapshot has been read in this process;
        #: the fail-closed guard in ``save`` keys off it.
        self.loaded = False

    # -- internals --------------------------------------------------------
    def _factory(self):
        """Resolve the session factory lazily: importing this module must not
        open a socket or read configuration (same rule as the engine proxy)."""
        if self._session_factory is None:
            from storage.relational.session import get_session_factory

            self._session_factory = get_session_factory()
        return self._session_factory

    @staticmethod
    def _encode(payload: dict[str, Any]) -> tuple[str, str]:
        blob = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        digest = hashlib.sha256(blob.encode("utf-8")).hexdigest()
        return blob, digest

    # -- store protocol ---------------------------------------------------
    def load(self) -> dict[str, Any] | None:
        """Return the stored payload, or None when this scope has no snapshot.

        Raises when the row exists but cannot be trusted (digest mismatch) or
        the backend is unreachable — callers treat that as "start empty".
        """
        factory = self._factory()
        with factory() as session:
            row = session.get(ContextSnapshot, (self.tenant_id, self.scope_key))
            if row is None:
                self.loaded = True
                return None
            blob = row.payload
            digest = row.content_sha256
            version = row.schema_version
        if not isinstance(blob, str) or not blob:
            raise RuntimeError(
                f"context snapshot for tenant={self.tenant_id!r} scope={self.scope_key!r} "
                "is empty; refusing to treat it as content")
        actual = hashlib.sha256(blob.encode("utf-8")).hexdigest()
        if actual != (digest or ""):
            raise RuntimeError(
                f"context snapshot for tenant={self.tenant_id!r} scope={self.scope_key!r} "
                "failed its integrity check (sha256 mismatch)")
        self.loaded = True
        payload = json.loads(blob)
        if isinstance(payload, dict):
            payload.setdefault("schema_version", version)
        return payload

    def save(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Upsert the snapshot for this scope and return a small receipt."""
        if not self.loaded:
            raise RuntimeError(
                "refusing to save a viking context snapshot before the existing "
                "one has been read in this process; a blind write could replace "
                "durable content that was never restored (TASK-MEM-010 fail-closed "
                "guard). Fix the backend and restart, or clear the row explicitly.")
        blob, digest = self._encode(payload)
        schema_version = int(payload.get("schema_version", 1))
        node_count = int(payload.get("node_count", 0))
        factory = self._factory()
        with factory() as session:
            row = session.get(ContextSnapshot, (self.tenant_id, self.scope_key))
            if row is None:
                row = ContextSnapshot(tenant_id=self.tenant_id, scope_key=self.scope_key)
                session.add(row)
            row.schema_version = schema_version
            row.payload = blob
            row.content_sha256 = digest
            row.node_count = node_count
            row.updated_at = get_utc_now()
            session.commit()
        # Receipt from locals: the session context closed above, so the ORM row
        # is detached and must not be touched again.
        return {
            "backend": "relational",
            "tenant_id": self.tenant_id,
            "scope_key": self.scope_key,
            "schema_version": schema_version,
            "node_count": node_count,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }


__all__ = [
    "DEFAULT_TENANT_ID",
    "RelationalContextSnapshotStore",
    "normalize_scope_key",
]
