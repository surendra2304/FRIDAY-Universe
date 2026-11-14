"""TASK-REL-031 (2026-11-15): a FRIDAY save must actually reach the shared store.

Live trace that motivated this suite (2026-11-15 ~02:56 IST, production):
"remember my calibration phrase is zircon-ember-731" through /api/chat was
answered "Saved on the local memory backend… Shared Memora synchronization
is not confirmed", yet direct inspection found the fact in BOTH stores under
different ids (shared 85ce0419…, local bdd353fa…). Memora's journal showed
the write pipeline's Gemini embedding calls completing ~2s into the write;
FRIDAY's client gave the write the generic 3.5s timeout, lost the response,
and fell back locally — silently (the failure was logged at DEBUG, and a
non-201 response was not logged at all). Nothing ever re-synced a local_only
fact afterwards, so any save whose write genuinely never landed stayed
invisible to the shared store forever.

The fix, exercised here against a stub shared Memora:
1. Writes use a dedicated write budget (``write_timeout``), not the 3.5s
   generic timeout.
2. Every logical save carries ONE client-generated idempotency key, sent
   before the first attempt; a lost response is retried once with the same
   key, and Memora's idempotency pre-check returns the very record the
   first attempt committed — no twins.
3. A save that still lands local_only queues a bounded background re-sync
   with the same key; on a confirmed shared landing the local placeholder
   is marked ``superseded`` so it stops shadowing the shared record.
4. A shared write failure is reported in the result (``sync_error``) and
   logged at WARNING, not swallowed at DEBUG.
5. The local recall candidate window is ordered by keyword match-count
   before importance, closing the REL-014 residual: a forget phrased with
   a distinguishing value returned not_found when 500+ common-keyword
   decoys outranked the low-importance target out of the window.
"""
from __future__ import annotations

import json
import socket
import sqlite3
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit]


# ---------------------------------------------------------------------------
# A stub "shared Memora" with the production response shape (no "status"
# field) and Memora's idempotency semantics (same key -> same record).
# ---------------------------------------------------------------------------

class _StubMemoraHandler(BaseHTTPRequestHandler):
    mode: str = "ok"  # "ok" | "fail" | "drop_first"
    posts: list = []
    stored: dict = {}
    dropped_once: bool = False

    def log_message(self, *args):  # keep the suite quiet
        pass

    def _send(self, status: int, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):  # noqa: N802 - BaseHTTPRequestHandler API
        if not self.path.startswith("/v1/memories"):
            self._send(404, b"{}")
            return
        length = int(self.headers.get("Content-Length") or 0)
        payload = json.loads(self.rfile.read(length) or b"{}")
        type(self).posts.append(payload)
        if type(self).mode == "fail":
            self._send(500, b'{"detail": "stub write failure"}')
            return
        key = payload.get("idempotency_key")
        if key and key in type(self).stored:
            self._send(201, json.dumps(type(self).stored[key]).encode())
            return
        record = {
            "id": str(uuid.uuid4()),
            "content_text": payload.get("content_text"),
            "memory_type": payload.get("memory_type", "episodic"),
            "lifecycle_state": "active",
            "idempotency_key": key,
            "storage_backend": "oracle",
            "storage_durable": True,
        }
        if key:
            type(self).stored[key] = record
        if type(self).mode == "drop_first" and not type(self).dropped_once:
            # The write COMMITTED (record stored above) but the response is
            # lost on the wire — the exact production failure shape.
            type(self).dropped_once = True
            self.close_connection = True
            try:
                self.connection.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            self.connection.close()
            return
        self._send(201, json.dumps(record).encode())

    def do_GET(self):  # noqa: N802
        if self.path.startswith("/v1/memories/search"):
            rows = list(type(self).stored.values())
            self._send(200, json.dumps(rows).encode())
        else:
            self._send(404, b"{}")

    def do_DELETE(self):  # noqa: N802
        self._send(404, b"{}")


@pytest.fixture()
def stub_memora():
    _StubMemoraHandler.mode = "ok"
    _StubMemoraHandler.posts = []
    _StubMemoraHandler.stored = {}
    _StubMemoraHandler.dropped_once = False
    server = ThreadingHTTPServer(("127.0.0.1", 0), _StubMemoraHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()


def _client(tmp_path: Path, stub, **overrides):
    from friday.memory.memora_client import MemoraClient

    port = stub.server_address[1]
    kwargs = dict(
        base_url=f"http://127.0.0.1:{port}",
        local_db_path=str(tmp_path / "rel030.db"),
        remote_enabled=True,
        write_timeout=5.0,
    )
    kwargs.update(overrides)
    return MemoraClient(**kwargs)


def _local_rows(db_path: str):
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute(
            "SELECT id, content_text, lifecycle_state FROM memory_records"
        ).fetchall()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# The lost-response save: retried with the same key, lands shared, no twin
# ---------------------------------------------------------------------------

def test_lost_response_retries_same_key_and_lands_shared(tmp_path, stub_memora):
    _StubMemoraHandler.mode = "drop_first"
    client = _client(tmp_path, stub_memora)
    try:
        res = client.record_fact(
            "friday", "my calibration phrase is zircon-ember-731", "owner_fact", 0.95
        )
        assert res["status"] == "success", res
        assert res["cloud"] is True
        # Two attempts, ONE idempotency key, and the returned id is the
        # record the first (dropped) attempt committed.
        assert len(_StubMemoraHandler.posts) == 2
        keys = {p.get("idempotency_key") for p in _StubMemoraHandler.posts}
        assert len(keys) == 1 and None not in keys
        committed = next(iter(_StubMemoraHandler.stored.values()))
        assert res["id"] == committed["id"]
        # No local twin was minted for a save that landed shared-side.
        assert _local_rows(str(tmp_path / "rel030.db")) == []
    finally:
        client._executor.shutdown(wait=True)


def test_shared_success_normalises_status(tmp_path, stub_memora):
    """Memora's write response has no "status" field; the client must
    normalise it so callers' stored-detection works off the real result."""
    client = _client(tmp_path, stub_memora)
    try:
        res = client.record_fact("friday", "my dog is named Bruno", "owner_fact", 0.95)
        assert res["status"] == "success"
        assert res["cloud"] is True
        assert res["id"]
    finally:
        client._executor.shutdown(wait=True)


# ---------------------------------------------------------------------------
# Persistent failure: honest local_only, then background re-sync converges
# ---------------------------------------------------------------------------

def test_local_only_resyncs_when_shared_store_recovers(tmp_path, stub_memora):
    _StubMemoraHandler.mode = "fail"
    client = _client(tmp_path, stub_memora)
    client.resync_delays = (0.2, 0.2, 0.2, 0.2)
    db_path = str(tmp_path / "rel030.db")
    try:
        res = client.record_fact(
            "friday", "my calibration phrase is zircon-ember-731", "owner_fact", 0.95
        )
        assert res["status"] == "local_only", res
        assert res["cloud"] is False
        assert res["sync_pending"] is True
        assert res["sync_error"] == "HTTP 500"
        rows = _local_rows(db_path)
        assert len(rows) == 1 and rows[0][2] == "active"
        local_id = rows[0][0]

        # The shared store recovers; the queued re-sync must land the fact
        # there under the SAME idempotency key and supersede the local row.
        _StubMemoraHandler.mode = "ok"
        deadline = time.time() + 10
        shared_id = None
        while time.time() < deadline:
            if _StubMemoraHandler.stored:
                shared_id = next(iter(_StubMemoraHandler.stored.values()))["id"]
                rows = _local_rows(db_path)
                if rows and rows[0][2] == "superseded":
                    break
            time.sleep(0.1)
        assert shared_id, "re-sync never landed the fact in the shared store"
        rows = _local_rows(db_path)
        assert rows[0][0] == local_id and rows[0][2] == "superseded", rows

        # Recall now serves the shared record; the superseded twin is gone.
        hits = client.recall_memories("friday", "calibration phrase", limit=5)
        assert any(h.get("id") == shared_id for h in hits), hits
        assert not any(h.get("id") == local_id for h in hits), hits
    finally:
        client._executor.shutdown(wait=True)


# ---------------------------------------------------------------------------
# REL-014 residual: forget with a distinguishing value outside the window
# ---------------------------------------------------------------------------

def test_forget_distinguishing_value_beyond_importance_window(tmp_path):
    """600 decoys share ONE subject keyword ('phrase') at importance 0.7;
    the target matches BOTH subject keywords at importance 0.20. Ordered
    by importance alone, the 500-row candidate window fills with decoys
    and forget answers not_found for a fact that is demonstrably stored."""
    from friday.memory.memora_client import MemoraClient

    client = MemoraClient(
        local_db_path=str(tmp_path / "window.db"), remote_enabled=False
    )
    try:
        for i in range(600):
            res = client._record_fact_locally(
                "friday", f"routine phrase log entry {i}", "owner_fact", 0.7
            )
            assert res["status"] == "success"
        client._record_fact_locally(
            "friday", 'my calibration phrase is "zircon ember 731"', "owner_fact", 0.20
        )
        out = client.forget_fact("friday", "my calibration phrase")
        assert out["status"] == "deleted", out
        hits = client.recall_memories("friday", "calibration phrase", limit=5)
        assert not any("zircon ember" in str(h.get("content_text", "")) for h in hits), hits
    finally:
        client._executor.shutdown(wait=True)


def test_write_timeout_budget_exceeds_generic_timeout(tmp_path):
    from friday.memory.memora_client import MemoraClient

    client = MemoraClient(
        local_db_path=str(tmp_path / "budget.db"), remote_enabled=False
    )
    try:
        # The whole defect class exists because writes were given the
        # generic 3.5s budget; the write budget must stay larger.
        assert client.write_timeout > client.timeout
    finally:
        client._executor.shutdown(wait=True)
