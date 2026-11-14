"""TASK-REL-029 regression tests: conversation history must survive restarts.

TASK-REL-023 established the defect: ``_conversation_history`` was a purely
in-memory ``deque`` in ``friday.api.server`` — every FRIDAY restart,
including every deploy, wiped the owner's conversation history entirely,
and the console restore (GET /api/v1/conversation/history) could only
return what the current process still held.

These tests pin the fixed behaviour through the real surfaces:

* turns are logged through ``_log_conversation`` — the exact helper the
  chat path funnels into (persist-first begin + finalize);
* reads go through the real HTTP restore endpoint the console uses;
* a "restart" is simulated by dropping the in-memory deque and the
  hydration flag — a fresh process would start exactly that empty, with
  only the durable store left to restore from.

On clean main there is no durable store and no hydration, so the
post-restart reads come back empty and the survival assertions fail.
The store is pointed at a throwaway SQLite file via
``FRIDAY_CONVERSATION_HISTORY_DB_PATH`` (the sanctioned test-only backend;
production uses Oracle through the same store class).
"""

from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

from friday.api import server
from friday.api.server import app

MARKER_A = "rel029-marker-alpha-turn"
MARKER_B = "rel029-marker-beta-turn"
MARKER_PENDING = "rel029-marker-pending-turn"
MARKER_POST = "rel029-marker-after-restart"


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture()
def durable_history(tmp_path, monkeypatch):
    """Isolate history state and point the durable store at a temp file."""
    db_file = tmp_path / "rel029_history.db"
    monkeypatch.setenv("FRIDAY_CONVERSATION_HISTORY_DB_PATH", str(db_file))

    saved_entries = list(server._conversation_history)
    saved_store = getattr(server, "_history_store", None)
    saved_failed = getattr(server, "_history_store_failed", False)
    saved_hydrated = getattr(server, "_history_hydrated", False)
    saved_pending = dict(getattr(server, "_history_pending_sync", {}))

    server._conversation_history.clear()
    if hasattr(server, "_history_store"):
        server._history_store = None
    if hasattr(server, "_history_store_failed"):
        server._history_store_failed = False
    if hasattr(server, "_history_hydrated"):
        server._history_hydrated = False
    if hasattr(server, "_history_hydrate_retry_after"):
        server._history_hydrate_retry_after = 0.0
    if hasattr(server, "_history_pending_sync"):
        server._history_pending_sync.clear()

    yield db_file

    server._conversation_history.clear()
    server._conversation_history.extend(saved_entries)
    if hasattr(server, "_history_store"):
        server._history_store = saved_store
    if hasattr(server, "_history_store_failed"):
        server._history_store_failed = saved_failed
    if hasattr(server, "_history_hydrated"):
        server._history_hydrated = saved_hydrated
    if hasattr(server, "_history_pending_sync"):
        server._history_pending_sync.clear()
        server._history_pending_sync.update(saved_pending)


def _simulate_restart() -> None:
    """Drop everything a process restart would drop — memory only."""
    server._conversation_history.clear()
    if hasattr(server, "_history_pending_sync"):
        server._history_pending_sync.clear()
    if hasattr(server, "_history_hydrated"):
        server._history_hydrated = False
    if hasattr(server, "_history_hydrate_retry_after"):
        server._history_hydrate_retry_after = 0.0


def _history(client: TestClient) -> list[dict]:
    resp = client.get("/api/v1/conversation/history", params={"limit": 50})
    assert resp.status_code == 200
    return resp.json().get("entries") or []


def _find(entries: list[dict], user_input: str) -> dict | None:
    for e in entries:
        if e.get("user_input") == user_input:
            return e
    return None


def _log(user_input: str, reply: str, **kwargs) -> None:
    asyncio.run(server._log_conversation(user_input, reply, **kwargs))


def test_history_survives_restart(client, durable_history):
    _log(MARKER_A, "reply alpha", agents_involved=["friday"], metadata={"probe": "a"})
    _log(MARKER_B, "reply beta")

    before = _history(client)
    assert _find(before, MARKER_A) is not None
    assert _find(before, MARKER_B) is not None

    _simulate_restart()

    after = _history(client)
    entry_a = _find(after, MARKER_A)
    entry_b = _find(after, MARKER_B)
    assert entry_a is not None, "history was lost across a restart"
    assert entry_b is not None, "history was lost across a restart"
    assert entry_a["friday_reply"] == "reply alpha"
    assert entry_a["status"] == "success"
    assert entry_a["agents_involved"] == ["friday"]
    assert entry_a["metadata"] == {"probe": "a"}
    assert entry_b["friday_reply"] == "reply beta"


def test_pending_turn_survives_restart(client, durable_history):
    """Persist-first semantics, now durable: a turn that never finalized
    (crash/hang mid-turn) still leaves the user's message behind — even
    when the process itself dies before the reply."""
    asyncio.run(server._begin_conversation_entry(MARKER_PENDING))

    _simulate_restart()

    entry = _find(_history(client), MARKER_PENDING)
    assert entry is not None, "pending user turn was lost across a restart"
    assert entry["status"] == "pending"
    assert entry["friday_reply"] == ""


def test_new_turns_append_alongside_restored_history(client, durable_history):
    _log(MARKER_A, "reply alpha")

    _simulate_restart()
    restored = _history(client)
    assert _find(restored, MARKER_A) is not None

    _log(MARKER_POST, "reply after restart")

    entries = _history(client)
    assert _find(entries, MARKER_POST) is not None
    assert _find(entries, MARKER_A) is not None
    # Newest first: the post-restart turn sorts ahead of the restored one.
    assert entries[0]["user_input"] == MARKER_POST


def test_second_restart_still_restores(client, durable_history):
    _log(MARKER_A, "reply alpha")
    _log(MARKER_B, "reply beta")

    _simulate_restart()
    first = _history(client)
    assert _find(first, MARKER_A) is not None
    assert _find(first, MARKER_B) is not None

    _simulate_restart()
    second = _history(client)
    assert _find(second, MARKER_A) is not None
    assert _find(second, MARKER_B) is not None


def test_clear_history_wipes_durable_store(client, durable_history):
    _log(MARKER_A, "reply alpha")
    assert _find(_history(client), MARKER_A) is not None

    asyncio.run(server.clear_conversation_history())
    assert _history(client) == []

    _simulate_restart()
    assert _history(client) == [], "cleared history resurrected after a restart"
