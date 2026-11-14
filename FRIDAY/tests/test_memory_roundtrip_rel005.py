"""TASK-REL-005 (2026-11-14): the remember → recall round-trip must not lie.

Production failure, verified live through the real console on 2026-11-14:
"remember my test phrase 'purple elephant 42'" was answered "Saved on the
local memory backend, Boss: [the entire raw instruction echoed back]…
Shared Memora synchronization is not confirmed", and 15 s later "What was
my test phrase?" was answered "I'm not seeing a record of a test phrase".

Three defects combined:
1. ``MemoraClient.record_fact`` falls back to the local store when the
   shared write fails (status ``local_only``), but ``recall_memories``
   treated a shared EMPTY search result as authoritative and never looked
   at the local store — the writer and the reader consulted different
   stores, so the save and the recall contradicted each other.
2. "What was my X?" matched none of the chat fast-path recall patterns, so
   the deterministic recall never ran; the question fell to the LLM, whose
   context comes from the shared store the fact never reached.
3. The remember payload extractor only stripped the command phrase when
   the message STARTED with it, so "FRIDAY, remember this for me: …"
   stored the entire raw instruction as the "fact".

These tests drive the SAME code paths the chat handler uses (the real
``MemoraClient`` against a stub shared-Memora HTTP service, and
``_dispatch_command`` itself) — not one store in isolation.
"""
from __future__ import annotations

import asyncio
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit]


# ---------------------------------------------------------------------------
# A stub "shared Memora" service: writes fail, searches answer empty —
# exactly the production shape that produced local_only saves.
# ---------------------------------------------------------------------------

class _StubMemoraHandler(BaseHTTPRequestHandler):
    search_results: list = []
    write_status: int = 500

    def log_message(self, *args):  # keep the suite quiet
        pass

    def _send(self, status: int, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802 - BaseHTTPRequestHandler API
        if self.path.startswith("/v1/memories/search"):
            self._send(200, json.dumps(type(self).search_results).encode())
        else:
            self._send(404, b"{}")

    def do_POST(self):  # noqa: N802
        self._send(type(self).write_status, b'{"detail": "stub write failure"}')

    def do_DELETE(self):  # noqa: N802
        self._send(404, b"{}")


@pytest.fixture()
def stub_memora():
    _StubMemoraHandler.search_results = []
    _StubMemoraHandler.write_status = 500
    server = ThreadingHTTPServer(("127.0.0.1", 0), _StubMemoraHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()


def _client(tmp_path: Path, stub, *, host: str = "127.0.0.1"):
    from friday.memory.memora_client import MemoraClient

    port = stub.server_address[1]
    return MemoraClient(
        base_url=f"http://{host}:{port}",
        local_db_path=str(tmp_path / "rel005.db"),
        remote_enabled=True,
    )


# ---------------------------------------------------------------------------
# Client level: writer store vs reader store
# ---------------------------------------------------------------------------

def test_local_only_write_is_recallable_when_shared_search_is_empty(tmp_path, stub_memora):
    """The production split: write fell back locally, shared search says
    'nothing here' — recall must still find what FRIDAY just saved."""
    client = _client(tmp_path, stub_memora)
    try:
        res = client.record_fact("friday", 'my test phrase is "crimson tiger 7"', "owner_fact", 0.95)
        assert res["status"] == "local_only"  # shared write failed, local save happened
        hits = client.recall_memories("friday", "test phrase", limit=5)
        assert any("crimson tiger 7" in str(h.get("content_text", "")) for h in hits), hits
    finally:
        client._executor.shutdown(wait=True)


def test_shared_and_local_results_merge_shared_first(tmp_path, stub_memora):
    """Shared rows stay primary (listed first), but a local_only fact is
    still present in the merged result — callers rank by subject overlap."""
    _StubMemoraHandler.search_results = [
        {"id": "shared-1", "content_text": "shared fact about chai", "memory_type": "semantic"}
    ]
    client = _client(tmp_path, stub_memora)
    try:
        client.record_fact("friday", 'my test phrase is "crimson tiger 7"', "owner_fact", 0.95)
        hits = client.recall_memories("friday", "test phrase", limit=5)
        assert hits[0]["id"] == "shared-1"
        assert any("crimson tiger 7" in str(h.get("content_text", "")) for h in hits), hits
    finally:
        client._executor.shutdown(wait=True)


def test_local_fact_survives_unrelated_shared_junk(tmp_path, stub_memora):
    """The exact live failure after the first fix iteration: the shared
    semantic search (min_score=0) returns an unrelated episodic dialogue
    row for almost any query, which used to crowd out the local fact
    entirely. The merged recall must still carry the local fact."""
    _StubMemoraHandler.search_results = [
        {"id": "ep-1", "content_text": 'FRIDAY, remember this for me: my test phrase is "purple elephant 42". Confirm what you stored.',
         "memory_type": "episodic"}
    ]
    client = _client(tmp_path, stub_memora)
    try:
        client.record_fact("friday", 'my test phrase is "crimson tiger 7"', "owner_fact", 0.95)
        hits = client.recall_memories("friday", "What was my test phrase", limit=10)
        assert any("crimson tiger 7" in str(h.get("content_text", "")) for h in hits), hits
    finally:
        client._executor.shutdown(wait=True)


def test_forgotten_local_only_fact_stays_forgotten(tmp_path, stub_memora):
    """Forget resolves its target through recall; a locally forgotten fact
    (lifecycle 'deleted') must never come back through the local fallback."""
    client = _client(tmp_path, stub_memora, host="localhost")
    try:
        client.record_fact("friday", 'my test phrase is "crimson tiger 7"', "owner_fact", 0.95)
        res = client.forget_fact("friday", "my test phrase")
        assert res["status"] == "deleted", res
        hits = client.recall_memories("friday", "test phrase", limit=5)
        assert not any("crimson tiger" in str(h.get("content_text", "")) for h in hits), hits
    finally:
        client._executor.shutdown(wait=True)


def test_local_recall_not_hidden_by_importance_window(tmp_path):
    """The local store's candidate window was 'top 100 rows by importance'
    across the whole multi-agent table — once 100+ accumulated rows
    outrank a fact, local recall can never see it again (the live
    verification's third failure layer). Candidate selection must be
    keyword-driven: a low-importance fact that matches the query is
    returned even with 150 higher-importance decoys present."""
    from friday.memory.memora_client import MemoraClient

    client = MemoraClient(local_db_path=str(tmp_path / "window.db"), remote_enabled=False)
    try:
        for i in range(150):
            res = client._record_fact_locally("friday", f"routine fleet note {i} about servers", "owner_fact", 0.95)
            assert res["status"] == "success"
        client._record_fact_locally("friday", 'my safe word is "amber falcon 3"', "owner_fact", 0.20)
        hits = client.recall_memories("friday", "amber falcon", limit=5)
        assert any("amber falcon 3" in str(h.get("content_text", "")) for h in hits), hits[:3]
    finally:
        client._executor.shutdown(wait=True)


def test_forget_local_only_fact_under_remote_config(tmp_path, stub_memora):
    """A local_only fact's id lives in the local store; forget used to fire
    a shared DELETE for that id, watch it 404, and report 'unconfirmed'
    without deleting anything. Forget must delete the record where it
    lives and report the local scope honestly."""
    client = _client(tmp_path, stub_memora)
    try:
        res = client.record_fact("friday", 'my safe word is "amber falcon 3"', "owner_fact", 0.55)
        assert res["status"] == "local_only"
        out = client.forget_fact("friday", "my safe word")
        assert out["status"] == "deleted", out
        assert out["cloud"] is False
        hits = client.recall_memories("friday", "safe word", limit=5)
        assert not any("amber falcon" in str(h.get("content_text", "")) for h in hits), hits
    finally:
        client._executor.shutdown(wait=True)


# ---------------------------------------------------------------------------
# Chat level: the exact production sequence through _dispatch_command
# ---------------------------------------------------------------------------

def test_chat_roundtrip_mid_sentence_remember_then_natural_recall(tmp_path, stub_memora, monkeypatch):
    from friday.api.server import _dispatch_command
    import friday.memory.memora_client as module

    client = _client(tmp_path, stub_memora)
    monkeypatch.setattr(module, "memora_client", client)
    try:
        saved = asyncio.run(_dispatch_command(
            'FRIDAY, remember this for me: my test phrase is "crimson tiger 7". Confirm what you stored.'
        ))
        assert saved["metadata"]["memory_store"] is True
        # The stored fact is the fact — not the vocative, not the command
        # wording, not the trailing meta-instruction.
        assert saved["metadata"]["fact"] == 'my test phrase is "crimson tiger 7".'
        assert "Confirm what you stored" not in saved["reply"]
        # The claim stays honest: local save, shared sync NOT confirmed.
        assert "local memory backend" in saved["reply"]
        assert "synchronization is not confirmed" in saved["reply"]

        recalled = asyncio.run(_dispatch_command("What was my test phrase?"))
        assert recalled is not None
        assert recalled["metadata"].get("memory_recall") is True
        assert "crimson tiger 7" in recalled["reply"]

        # The fact lives in the local store; forgetting it must delete it
        # there (not fire a shared DELETE for a local id and give up).
        forgotten = asyncio.run(_dispatch_command("forget my test phrase"))
        assert forgotten["metadata"].get("forget_status") == "deleted", forgotten
        assert "local memory backend" in forgotten["reply"]

        recalled_after = asyncio.run(_dispatch_command("What was my test phrase?"))
        assert "crimson tiger 7" not in recalled_after["reply"]
    finally:
        client._executor.shutdown(wait=True)


@pytest.mark.parametrize("message,expected_fact", [
    ("remember my favourite chai is masala chai", "my favourite chai is masala chai"),
    ("remember this: the gate code is 4419", "the gate code is 4419"),
    ("please remember that the gate code is 4419", "the gate code is 4419"),
    ("don't forget my anniversary is on May 3", "my anniversary is on May 3"),
    ("hey friday, remember that my locker number is 12", "my locker number is 12"),
    ('FRIDAY, remember this for me: my test phrase is "crimson tiger 7". Confirm what you stored.',
     'my test phrase is "crimson tiger 7".'),
])
def test_remember_payload_extraction(message, expected_fact, monkeypatch):
    from friday.api.server import _dispatch_command
    from friday.memory.memora_client import memora_client

    captured = {}

    def fake_record_fact(**kwargs):
        captured.update(kwargs)
        return {"status": "success", "id": "fixture"}

    monkeypatch.setattr(memora_client, "record_fact", fake_record_fact)
    result = asyncio.run(_dispatch_command(message))
    assert result["metadata"]["memory_store"] is True
    assert captured["fact_text"] == expected_fact
    assert result["metadata"]["fact"] == expected_fact
