"""TASK-FRD-016 (2026-11-16): the recall path stacked independent
Memora draws serially; the voice brain turn paid the sum.

Production decomposition (FRD-005 re-run #5 + staging probes,
2026-11-16): the recall gate's dispatch was one ``recall_memories``
call in the common case, but (a) inside the client, the remote hybrid
search and the local recall ran SERIALLY — on the loaded host the
remote leg alone consumed the full 15s recall budget while the ~0.1s
local leg waited behind it; and (b) for a spelling-variant question
("favourite colour" vs the stored US spelling) the FRD-014
canonical-variant draw ran only AFTER the primary draw returned,
inside the retry loop — a second full search stacked on the first.

Fix: both pairs of independent draws now run concurrently and merge
with the exact rules they had serially (client: remote-first merge
with REL-005/REL-022 dedupe; gate: retry-loop dedupe + the same
unpresentable filter). These tests pin the concurrency (draws overlap
in time), the draw COUNT (the retry loop must not re-pay for the
variant it already has), and the unchanged merge/answer semantics.
"""
from __future__ import annotations

import asyncio
import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

pytestmark = [pytest.mark.unit]

TEAL_CLEAN = "my favorite color is teal."
CHAI = "my favorite chai is masala chai and I review the fleet every morning at 9"
ZQ = "my secret favorite number is owner favorite test marker ZQ1794340686"


def _hits(*texts):
    return [
        {"id": f"hit-{i}", "content_text": t, "memory_type": "episodic"}
        for i, t in enumerate(texts)
    ]


# ---------------------------------------------------------------------------
# Gate level: primary + spelling-variant draws overlap; answer unchanged
# ---------------------------------------------------------------------------

class _TimedVariantMemora:
    """UK-spelled draw misses the fact; the canonical US draw finds it.
    Every draw records its (start, end) span so the test can prove the
    two draws overlapped instead of stacking."""

    def __init__(self, delay=0.6):
        self.delay = delay
        self.spans = []  # (query, start, end)
        self._lock = threading.Lock()

    def recall_memories(self, agent_name, query, limit=10):
        start = time.perf_counter()
        try:
            time.sleep(self.delay)
            if "favourite" in query:
                return _hits(CHAI, ZQ)
            return _hits(TEAL_CLEAN)
        finally:
            with self._lock:
                self.spans.append((query, start, time.perf_counter()))


def test_gate_fires_variant_draw_concurrently_with_primary(monkeypatch):
    from friday.api.server import _dispatch_command
    import friday.memory.memora_client as module

    fake = _TimedVariantMemora()
    monkeypatch.setattr(module, "memora_client", fake)
    result = asyncio.run(_dispatch_command("What is my favourite colour?"))

    # Same answer the serial FRD-014 retry produced.
    assert result["metadata"].get("spoken_summary") == "Your favorite color is teal."
    # Exactly two draws: primary + variant. The retry loop must NOT pay
    # for the variant a second time once the merged set full-matches.
    assert len(fake.spans) == 2
    (_, s1, e1), (_, s2, e2) = sorted(fake.spans, key=lambda sp: sp[1])
    # The second draw started before the first finished: they overlapped
    # (serial stacking would put s2 >= e1 by construction).
    assert s2 < e1


def test_gate_us_question_still_draws_once(monkeypatch):
    # The common case is unchanged: no spelling variant exists for the
    # US form, the primary draw full-matches, and nothing else fires.
    from friday.api.server import _dispatch_command
    import friday.memory.memora_client as module

    class _CountingMemora:
        def __init__(self):
            self.calls = 0

        def recall_memories(self, agent_name, query, limit=10):
            self.calls += 1
            return _hits(TEAL_CLEAN)

    fake = _CountingMemora()
    monkeypatch.setattr(module, "memora_client", fake)
    result = asyncio.run(_dispatch_command("What is my favorite color?"))
    assert result["metadata"].get("spoken_summary") == "Your favorite color is teal."
    assert fake.calls == 1


def test_gate_variant_failure_degrades_to_primary_set(monkeypatch):
    # A failing variant draw must not poison the primary result: the
    # gate answers from the primary set exactly as if no variant existed
    # (and the retry loop may still re-try the variant serially).
    from friday.api.server import _dispatch_command
    import friday.memory.memora_client as module

    class _FlakyVariantMemora:
        def recall_memories(self, agent_name, query, limit=10):
            if "favourite" in query:
                return _hits(CHAI, ZQ)
            if "favorite" in query and "colour" not in query:
                raise RuntimeError("variant draw exploded")
            return _hits(CHAI, ZQ)

    monkeypatch.setattr(module, "memora_client", _FlakyVariantMemora())
    result = asyncio.run(_dispatch_command("What is my favourite colour?"))
    # No teal anywhere reachable -> honest list answer, no exception.
    assert result["metadata"].get("memory_recall") is True
    assert "teal" not in result["reply"]


# ---------------------------------------------------------------------------
# Client level: remote + local legs overlap; merge semantics unchanged
# ---------------------------------------------------------------------------

class _SlowSearchHandler(BaseHTTPRequestHandler):
    delay = 0.5
    status = 200
    results = [{"id": "remote-1", "content_text": "shared store fact", "memory_type": "semantic"}]
    spans: list = []

    def log_message(self, *args):
        pass

    def do_GET(self):  # noqa: N802 - BaseHTTPRequestHandler API
        start = time.perf_counter()
        try:
            if self.path.startswith("/v1/memories/search"):
                time.sleep(type(self).delay)
                body = json.dumps(type(self).results).encode()
                self.send_response(type(self).status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            else:
                self.send_response(404)
                self.end_headers()
        finally:
            type(self).spans.append(("remote", start, time.perf_counter()))


@pytest.fixture()
def slow_memora():
    _SlowSearchHandler.delay = 0.5
    _SlowSearchHandler.status = 200
    _SlowSearchHandler.spans = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), _SlowSearchHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()


def _client_with_slow_local(stub, local_delay=0.5):
    from friday.memory.memora_client import MemoraClient

    port = stub.server_address[1]
    client = MemoraClient(
        base_url=f"http://127.0.0.1:{port}",
        local_db_path=None,
        remote_enabled=True,
    )
    spans = []

    def _slow_local(agent_name, query, limit):
        start = time.perf_counter()
        try:
            time.sleep(local_delay)
            return [{"id": "local-1", "content_text": "local store fact", "memory_type": "semantic"}]
        finally:
            spans.append(("local", start, time.perf_counter()))

    client._recall_locally = _slow_local  # noqa: SLF001 - test seam
    return client, spans


def test_client_recall_legs_run_concurrently(slow_memora):
    client, local_spans = _client_with_slow_local(slow_memora)
    t0 = time.perf_counter()
    hits = client.recall_memories("friday", "test phrase", limit=5)
    wall = time.perf_counter() - t0

    # Merge semantics unchanged: shared store primary, local appended.
    assert [h["id"] for h in hits] == ["remote-1", "local-1"]
    # The legs overlapped: total wall is far below the serial sum (1.0s).
    assert wall < 0.9
    (_, ls, le) = local_spans[0]
    (_, rs, re_) = _SlowSearchHandler.spans[0]
    assert ls < re_ and rs < le


def test_client_recall_remote_failure_still_returns_local(slow_memora):
    _SlowSearchHandler.status = 500
    client, _ = _client_with_slow_local(slow_memora, local_delay=0.05)
    hits = client.recall_memories("friday", "test phrase", limit=5)
    assert [h["id"] for h in hits] == ["local-1"]
