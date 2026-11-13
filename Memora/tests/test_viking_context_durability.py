"""TASK-MEM-010 — viking:// context durability regression tests.

Proves the recovery contract end to end:

* content written through the same code path the ``POST /v1/context/write``
  route uses (``MemoraContextService.write``) survives a restart: a second,
  freshly-constructed ``PersistentContextDatabase`` against the same
  file-backed SQLite test backend returns it via read, scoped search and
  layered recall (L0/L1/L2);
* tenant isolation after restore: a snapshot restored under tenant A is
  invisible to a service constructed for tenant B (and vice versa), following
  the ``access_scope`` fail-closed conventions (unknown key pair matches
  nothing);
* soft failure: an unavailable snapshot store starts an empty context with an
  honest log, and later writes refuse to overwrite durable content that was
  never read this process (no silent wipe);
* integrity: a tampered snapshot fails its sha256 check and starts empty
  instead of restoring half-trusted content;
* the API routes themselves (write → process restart → read/search/stats)
  restore through the real ``/v1/context/*`` surface.

SQLite appears here only as the explicitly-passed test backend (conftest pins
``MEMORA_ENV=testing``); production paths remain Oracle-only via
``storage.relational.session``.
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from core.memory.context_durability import RelationalContextSnapshotStore
from core.memory.context_service import MemoraContextService
from core.memory.real_viking_context import PersistentContextDatabase
from storage.relational.base import Base

MEMORA_URI = (
    "viking://user/memora/memories/fact/durable-postgres-note.md"
)
MEMORA_CONTENT = (
    "---\n"
    "title: Durable Postgres note\n"
    "kind: fact\n"
    "---\n\n"
    "# Durable Postgres note\n\n"
    "The staging database is Postgres 16 and its snapshots survive restarts.\n"
    "- API: FastAPI\n"
    "- Queue: Redis\n"
)


@pytest.fixture()
def sqlite_factory(tmp_path):
    """A file-backed SQLite session factory — the test-only durable backend.

    A *file* (not in-memory) database is the point: two service instances
    built one after the other share the durable rows, which is exactly the
    process-restart shape the recovery proof needs.
    """
    engine = create_engine(f"sqlite:///{tmp_path / 'viking_context.db'}")
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    try:
        yield factory
    finally:
        engine.dispose()


def make_service(factory, tenant_id="tenant-a", scope_key="memora",
                 user="memora") -> MemoraContextService:
    store = RelationalContextSnapshotStore(
        tenant_id=tenant_id, scope_key=scope_key, session_factory=factory)
    database = PersistentContextDatabase.restore_or_empty(store, user=user)
    return MemoraContextService(user=user, database=database)


def test_viking_context_survives_restart_with_layered_recall(sqlite_factory):
    """The recovery proof: write → fresh instance → search and layered recall."""
    first = make_service(sqlite_factory)

    # Same code path the POST /v1/context/write route calls into.
    written = first.write(MEMORA_URI, MEMORA_CONTENT, tags=("fact", "postgres"))
    assert written["uri"] == MEMORA_URI

    remembered = first.remember("decision", "snapshot design",
                                "Snapshot whole state per mutation",
                                "We decided to snapshot the whole viking state after every mutation.")
    assert remembered["uri"].startswith("viking://user/memora/memories/decision/")
    assert first.db.last_snapshot["state"] == "saved"
    assert first.db.last_snapshot["tenant_id"] == "tenant-a"

    # A second, fresh service against the same durable backend — the restart.
    second = make_service(sqlite_factory)
    assert second.db.last_snapshot["state"] == "restored"
    assert second.db.last_snapshot["files"] >= 2

    # Full text survives verbatim.
    assert second.read(MEMORA_URI, "L2")["content"] == MEMORA_CONTENT
    # Layered projections are all present after restore (L0 abstract, L1
    # overview, L2 full) — the metadata ScopedSearchEngine/LayerProjector
    # depend on came back with the nodes.
    assert "Postgres 16" in second.read(MEMORA_URI, "L0")["content"]
    assert "Durable Postgres note" in second.read(MEMORA_URI, "L1")["content"]
    assert second.read(MEMORA_URI, "L2")["content"].endswith("- Queue: Redis\n")

    # Scoped search and layered recall find the persisted content.
    hits = second.recall("Postgres snapshots survive", level="L1")
    assert hits, "restored content must be searchable"
    assert MEMORA_URI in [hit["uri"] for hit in hits]
    level, layered = second.recall_layered("staging database Postgres")
    assert level in ("L0", "L1", "L2")
    assert any(hit["uri"] == MEMORA_URI for hit in layered)

    # The remembered decision round-trips too.
    decision_hits = second.recall("snapshot whole viking state", level="L1")
    assert any(hit["uri"] == remembered["uri"] for hit in decision_hits)

    # Session-id sequence and commit history are part of the snapshot.
    assert second.db._sequence == first.db._sequence
    assert len(second.db.commits) == len(first.db.commits)


def test_session_commit_archive_survives_restart(sqlite_factory):
    first = make_service(sqlite_factory)
    result = first.commit_session("s-001", [
        {"role": "user", "content": "Remember to checkpoint the WAL before deploys."},
        {"role": "assistant", "content": "We have decided to checkpoint before every deploy."},
    ])
    assert result["committed"] is True

    second = make_service(sqlite_factory)
    restored = second.read(result["archive_uri"], "L2")
    assert "checkpoint the WAL" in restored["content"]
    # The memory files the original commit_session wrote (archive + extracted
    # memories) are part of the snapshot, so they come back with the tree.
    memories = [entry["uri"] for entry in second.ls("viking://user/memora/memories/decision")]
    assert memories, "committed session memories must survive the restart"


def test_tenant_isolation_after_restore(sqlite_factory):
    """Tenant A's snapshot is invisible to tenant B after restore, both ways."""
    tenant_a = make_service(sqlite_factory, tenant_id="tenant-a")
    tenant_a.write(MEMORA_URI, MEMORA_CONTENT, tags=("fact",))

    tenant_b = make_service(sqlite_factory, tenant_id="tenant-b")
    # Fail-closed: an unknown (tenant, scope) pair matches nothing — B starts
    # with only the standard directory skeleton, never A's content.
    assert tenant_b.db.last_snapshot["state"] == "empty"
    with pytest.raises(KeyError):
        tenant_b.read(MEMORA_URI, "L2")
    assert tenant_b.recall("Postgres 16") == []
    assert tenant_b.recall_layered("staging database")[1] == []

    # B writes its own content; A's restore must not see it either.
    tenant_b_uri = "viking://user/memora/memories/fact/tenant-b-local.md"
    tenant_b.write(tenant_b_uri, "# Tenant B local\n\nOnly tenant B knows this.\n")

    tenant_a_again = make_service(sqlite_factory, tenant_id="tenant-a")
    assert tenant_a_again.read(MEMORA_URI, "L2")["content"] == MEMORA_CONTENT
    with pytest.raises(KeyError):
        tenant_a_again.read(tenant_b_uri, "L2")
    assert all(hit["uri"] != tenant_b_uri
               for hit in tenant_a_again.recall("Only tenant B knows"))


def test_unavailable_store_starts_empty_and_never_wipes_unread_snapshot(
        sqlite_factory, caplog):
    """Soft-fail startup: empty context + honest log; saves stay fail-closed."""
    healthy_store = RelationalContextSnapshotStore(
        tenant_id="tenant-a", scope_key="memora", session_factory=sqlite_factory)

    # Simulate a transient backend outage at startup: the row exists (write it
    # through a healthy instance first) but load() raises.
    healthy = PersistentContextDatabase.restore_or_empty(healthy_store, user="memora")
    healthy.write(MEMORA_URI, MEMORA_CONTENT, tags=("fact",))
    assert healthy_store.loaded

    broken_store = RelationalContextSnapshotStore(
        tenant_id="tenant-a", scope_key="memora", session_factory=sqlite_factory)
    original_load = RelationalContextSnapshotStore.load

    def broken_load(self):
        raise RuntimeError("backend down")

    RelationalContextSnapshotStore.load = broken_load
    try:
        with caplog.at_level("WARNING"):
            restored = PersistentContextDatabase.restore_or_empty(
                broken_store, user="memora")
        # Fail-soft: an empty, working context — never a crash, never
        # fabricated content standing in for the unread snapshot.
        assert restored.stats()["files"] == 0
        assert restored.last_snapshot["state"] == "empty"
        assert "starting with an empty context database" in caplog.text
        assert "backend down" in caplog.text

        # Fail-closed writes: a process that never read the existing snapshot
        # must not overwrite it with content built from an empty start.
        with pytest.raises(RuntimeError, match="refusing to save"):
            restored.write(MEMORA_URI, MEMORA_CONTENT, tags=("fact",))
    finally:
        RelationalContextSnapshotStore.load = original_load

    # Recovery: once the backend answers again, a fresh process restores the
    # untouched snapshot (the blocked write never reached the store).
    recovered = make_service(sqlite_factory)
    assert recovered.read(MEMORA_URI, "L2")["content"] == MEMORA_CONTENT


def test_tampered_snapshot_fails_integrity_and_starts_empty(sqlite_factory, tmp_path, caplog):
    """A digest mismatch is treated as an unavailable store, not trusted data."""
    first = make_service(sqlite_factory)
    first.write(MEMORA_URI, MEMORA_CONTENT, tags=("fact",))

    # Corrupt the durable row out-of-band (simulated bit rot / tampering).
    engine = create_engine(f"sqlite:///{tmp_path / 'viking_context.db'}")
    with engine.begin() as connection:
        connection.execute(text(
            "UPDATE context_snapshots SET payload = '{\"nodes\": [], \"fabricated\": true}' "
            "WHERE tenant_id = 'tenant-a' AND scope_key = 'memora'"))
    engine.dispose()

    with caplog.at_level("WARNING"):
        second = make_service(sqlite_factory)
    assert second.stats()["files"] == 0
    assert second.db.last_snapshot["state"] == "empty"
    assert "integrity check" in caplog.text
    assert second.recall("Postgres") == []


def test_api_routes_restore_content_after_service_rebuild(client, monkeypatch):
    """The real /v1/context surface: write → rebuild → read/search/stats."""
    from apps.api.routers import context_db as context_db_module

    original_default = context_db_module._service._default
    try:
        response = client.post("/v1/context/write", json={
            "uri": MEMORA_URI,
            "content": MEMORA_CONTENT,
            "tags": ["fact", "postgres"],
        })
        assert response.status_code == 200
        assert response.json()["uri"] == MEMORA_URI

        # Simulate a process restart: drop the shared singleton; the next
        # route call reconstructs the service from the durable snapshot.
        monkeypatch.setattr(context_db_module._service, "_default", None)

        stats = client.get("/v1/context/stats").json()
        assert stats["durability"]["state"] == "restored"

        read = client.get("/v1/context/read",
                          params={"uri": MEMORA_URI, "level": "L2"}).json()
        assert read["content"] == MEMORA_CONTENT

        search = client.get("/v1/context/search",
                            params={"query": "Postgres snapshots survive",
                                    "level": "L1"}).json()
        assert search["hits"], "restored content must be searchable via the API"
        assert search["hits"][0]["uri"] == MEMORA_URI
    finally:
        context_db_module._service._default = original_default
