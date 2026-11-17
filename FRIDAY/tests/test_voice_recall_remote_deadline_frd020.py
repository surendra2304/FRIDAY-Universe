"""TASK-FRD-020 (2026-11-17): read-only recall must not wait out a
stalled Memora remote leg when the local leg already has the answer.

Production decomposition (FRD-005 re-run #8, 2026-11-17; issue #35
comment 6934443810): the recall-gem brain turn took 15.69s against
1.90s for the identical colour shape on a calm host. Journal
segmentation (~/workspace/voice-brain-latency/STATE.md) proved the
seconds: Memora's journal is totally silent for ~51s spanning the
gem draw (05:56:47.106 -> 05:57:38.104 IST; Futuris's 15s event
polls miss three beats and FRIDAY's own Memora cursor read times
out at 05:57:21 — two independent witnesses), and the gem search
never appears in Memora's access log. Inside the client,
TASK-FRD-016 had parallelised the remote/local legs but left an
UNBOUNDED ``_remote_thread.join()``: the caller still paid the
remote leg's full ``recall_timeout`` (15.0s) while the local leg's
10 hits sat ready (bridge send 05:56:55.42 + ~0.5s entry + 15.0s
= the draw's return at 05:57:11.0, exact).

Fix: ``recall_join_deadline`` (constructor / env
FRIDAY_MEMORA_RECALL_JOIN_DEADLINE_S, default 5.0s) bounds the
caller's WAIT for read-only recall only. A remote leg that
outlives it is treated exactly like a remote error — the local
answer stands and the daemon thread finishes unobserved. The
remote request keeps its full recall_timeout socket budget
(WF015 contract untouched), mutation recall (for_mutation=True)
is exempt (REL-022 twin resolution needs the authoritative remote
picture), and a deadline <= 0 restores the pre-fix wait.
"""
from __future__ import annotations

import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

pytestmark = [pytest.mark.unit]


class _SearchHandler(BaseHTTPRequestHandler):
    delay = 0.2
    results = [{"id": "remote-1", "content_text": "shared store fact", "memory_type": "semantic"}]

    def log_message(self, *args):  # keep test output clean
        pass

    def do_GET(self):  # noqa: N802 - BaseHTTPRequestHandler API
        if self.path.startswith("/v1/memories/search"):
            time.sleep(type(self).delay)
            body = json.dumps(type(self).results).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()


@pytest.fixture()
def memora_stub():
    _SearchHandler.delay = 0.2
    server = ThreadingHTTPServer(("127.0.0.1", 0), _SearchHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()


def _client(stub, **kwargs):
    from friday.memory.memora_client import MemoraClient

    port = stub.server_address[1]
    client = MemoraClient(
        base_url=f"http://127.0.0.1:{port}",
        local_db_path=None,
        remote_enabled=True,
        **kwargs,
    )

    def _fast_local(agent_name, query, limit):
        return [{"id": "local-1", "content_text": "local store fact", "memory_type": "semantic"}]

    client._recall_locally = _fast_local  # noqa: SLF001 - test seam
    return client


def test_slow_remote_past_deadline_returns_local_fast(memora_stub):
    _SearchHandler.delay = 3.0
    client = _client(memora_stub, recall_join_deadline=0.5)
    t0 = time.perf_counter()
    hits = client.recall_memories("friday", "what is my favorite gem", limit=5)
    wall = time.perf_counter() - t0
    # The local answer stands; the caller did NOT wait out the remote
    # leg (3.0s server delay, 15s default socket budget).
    assert [h["id"] for h in hits] == ["local-1"]
    assert wall < 2.0


def test_remote_within_deadline_still_merges(memora_stub):
    _SearchHandler.delay = 0.2
    client = _client(memora_stub, recall_join_deadline=2.0)
    hits = client.recall_memories("friday", "what is my favorite gem", limit=5)
    # Merge semantics unchanged: shared store primary, local appended.
    assert [h["id"] for h in hits] == ["remote-1", "local-1"]


def test_mutation_recall_ignores_deadline(memora_stub):
    _SearchHandler.delay = 1.0
    client = _client(memora_stub, recall_join_deadline=0.3)
    t0 = time.perf_counter()
    hits = client.recall_memories("friday", "teal", limit=5, for_mutation=True)
    wall = time.perf_counter() - t0
    # REL-022: mutation resolution waits for the authoritative remote
    # picture even past the read-only deadline.
    assert [h["id"] for h in hits] == ["remote-1", "local-1"]
    assert wall >= 1.0


def test_deadline_disabled_waits_for_remote(memora_stub):
    _SearchHandler.delay = 1.0
    client = _client(memora_stub, recall_join_deadline=0)
    t0 = time.perf_counter()
    hits = client.recall_memories("friday", "what is my favorite gem", limit=5)
    wall = time.perf_counter() - t0
    # <= 0 disables the bound: pre-FRD-020 behaviour, caller waits.
    assert [h["id"] for h in hits] == ["remote-1", "local-1"]
    assert wall >= 1.0


def test_default_join_deadline_is_five_seconds(memora_stub, monkeypatch):
    monkeypatch.delenv("FRIDAY_MEMORA_RECALL_JOIN_DEADLINE_S", raising=False)
    client = _client(memora_stub)
    assert client.recall_join_deadline == 5.0
