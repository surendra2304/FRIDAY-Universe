"""
TASK-MEM-031 — Memora verify wave 3: claude-mem needles + agentmemory confidence.

Locks the two adaptations and their production wiring:

- claude-mem (thedotmack/claude-mem): the needle taxonomy
  (``core.memory.session_needles``) classifies every captured event,
  ``capture_event`` stores the kind in provenance, the L0 session index
  rides in the session-start pack, and ``GET /v1/capture/sessions``
  serves it. ``sensitive`` needles never render their content in a
  timeline or a detail read.
- agentmemory (rohitg00/agentmemory): confidence learns from use
  (``core.memory.confidence_reinforcement``) — the explicit
  ``POST /v1/capture/recall-outcome`` path, the implicit bump when a
  digest is promoted to SEMANTIC, and confidence-weighted ordering in
  the session-start inject pack.
- Forge wire: ``ForgeAdapter.record_session_observation`` classifies +
  stores Forge observations with the same taxonomy (sensitive content
  withheld at write time).

Runs in the Memora tier-1 CI step (listed in
.github/workflows/friday-universe-ci.yml).
"""
import importlib

import pytest

from adapters.adapter_registry import adapter_registry
from core.identity.service import IdentityService
from core.memory.capture_service import SessionCaptureService
from core.memory.confidence_reinforcement import (
    clamp_confidence,
    confidence_weighted_score,
    confidence_weighted_sort,
    reinforce_on_recall,
)
from core.memory.session_needles import classify_needle, detail, list_actor_sessions, timeline
from storage.relational.models import MemoryRecord

oracle_module = importlib.import_module("storage.vector.oracle_vector_adapter")


class StubOracleAdapter:
    """Vector boundary stub (same pattern as the MEM-01 suite): no
    semantic hits, so recall is the keyword leg — deterministic."""

    def is_oracle_backend(self):
        return True

    def search_similarity(self, query_vector, limit, tenant_id, score_threshold, db=None):
        return []


@pytest.fixture(autouse=True)
def _no_vector(monkeypatch):
    monkeypatch.setattr(oracle_module, "oracle_vector_adapter", StubOracleAdapter())


def _setup(test_db):
    IdentityService.register_agent(test_db, "friday")


def _capture(client, session_id, kind, content):
    return client.post(
        "/v1/capture/events",
        json={"session_id": session_id, "kind": kind, "content": content},
    )


# ---------------------------------------------------------------------------
# claude-mem: needle classification
# ---------------------------------------------------------------------------


def test_classify_needle_kinds():
    assert classify_needle("Decided to keep Redis and Qdrant until the ARM server is allocated.") == "decision"
    assert classify_needle("Fixed the crash in the deploy probe; the regression is gone.") == "bugfix"
    assert classify_needle("Found a SQL injection vulnerability in the login form.") == "security_alert"
    assert classify_needle("This note is confidential, do not share it with anyone.") == "sensitive"
    assert classify_needle("Use TLS for the callback and audit the permission checks.") == "security_note"
    assert classify_needle("Implement support for a new feature: nightly vault export.") == "feature"
    assert classify_needle("Refactor the capture loop to extract the digest builder.") == "refactor"
    assert classify_needle("Turns out the cache key was the problem all along.") == "discovery"
    assert classify_needle("Update the retention window from 30 days to 90 days.") == "change"
    assert classify_needle("Ran the fleet health probe; all ten agents returned 200.") == "observation"
    assert classify_needle("") == "observation"


def test_classify_needle_priority_security_and_sensitive_win():
    # A fix for a vulnerability is a security alert, not a bugfix.
    assert classify_needle("Fixed the SQL injection vulnerability in auth.") == "security_alert"
    # A decision about a secret is sensitive, not a decision.
    assert classify_needle("Decided to rotate the api key after the incident.") == "sensitive"


def test_capture_event_stores_needle_kind(client, test_db):
    _setup(test_db)
    resp = _capture(
        client, "sess-needle-1", "decision",
        "Decided to keep Redis and Qdrant until the ARM server is allocated.",
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["stored"] is True, body
    assert body["needle_kind"] == "decision", body
    stored = test_db.query(MemoryRecord).filter(MemoryRecord.id == body["id"]).one()
    assert (stored.provenance or {}).get("needle_kind") == "decision"
    assert (stored.provenance or {}).get("event_kind") == "decision"


def test_sensitive_event_withheld_from_timeline_and_detail(client, test_db):
    _setup(test_db)
    resp = _capture(
        client, "sess-needle-2", "note",
        "This note is confidential, do not share it with anyone.",
    )
    assert resp.json()["needle_kind"] == "sensitive", resp.json()
    event_id = resp.json()["id"]

    tl = timeline(test_db, actor_name="friday", session_id="sess-needle-2")
    assert tl["event_count"] == 1
    assert tl["needles"] == {"sensitive": 1}
    assert "confidential" not in tl["timeline"]
    assert "withheld" in tl["timeline"]

    det = detail(test_db, event_id=event_id, actor_name="friday")
    assert det["found"] is True
    assert det["needle_kind"] == "sensitive"
    assert det["withheld"] is True
    assert det["content"] is None

    # A non-sensitive event in the same session still reads in full.
    resp2 = _capture(client, "sess-needle-2", "decision", "Decided to keep Redis for now.")
    det2 = detail(test_db, event_id=resp2.json()["id"], actor_name="friday")
    assert det2["withheld"] is False
    assert "Decided to keep Redis" in (det2["content"] or "")


def test_session_index_over_http(client, test_db):
    _setup(test_db)
    _capture(client, "sess-idx-a", "decision", "Decided to keep Redis and Qdrant for now.")
    _capture(client, "sess-idx-a", "tool_call", "Ran the fleet health probe; all ten agents returned 200.")
    _capture(client, "sess-idx-b", "tool_call", "Fixed the crash in the deploy probe.")

    resp = client.get("/v1/capture/sessions")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    sessions = {s["session_id"]: s for s in body["sessions"]}
    assert {"sess-idx-a", "sess-idx-b"} <= set(sessions), body
    assert sessions["sess-idx-a"]["event_count"] == 2
    assert sessions["sess-idx-a"]["needles"]["decision"] == 1
    assert sessions["sess-idx-a"]["tokens"] >= 1
    assert sessions["sess-idx-b"]["needles"]["bugfix"] == 1
    assert "sess-idx-a" in body["index"] and "sess-idx-b" in body["index"]
    assert "tokens" in body["index"]


def test_context_pack_carries_session_index(client, test_db):
    _setup(test_db)
    _capture(client, "sess-ctx-1", "decision", "Decided to keep Redis and Qdrant for now.")
    resp = client.get("/v1/capture/context", params={"q": "Redis Qdrant"})
    assert resp.status_code == 200, resp.text
    pack = resp.json()
    assert pack["hit_count"] >= 1, pack
    assert "Redis and Qdrant" in pack["context"]
    assert pack["session_index"], pack
    assert any(s["session_id"] == "sess-ctx-1" for s in pack["session_index"])
    assert "Session sess-ctx-1" in pack["context"]


def test_capture_routes_include_new_endpoints():
    from apps.api.main import app

    paths = set(app.openapi()["paths"])
    assert {"/v1/capture/events", "/v1/capture/compress", "/v1/capture/context", "/v1/capture/handoff"} <= paths
    assert "/v1/capture/sessions" in paths
    assert "/v1/capture/recall-outcome" in paths


# ---------------------------------------------------------------------------
# agentmemory: confidence learns from use
# ---------------------------------------------------------------------------


def test_confidence_weighted_sort_flips_order_on_confidence():
    class _FakeRecord:
        def __init__(self, rid, confidence):
            self.id = rid
            self.confidence = confidence

    class _FakeHit:
        def __init__(self, rid, final_score, confidence):
            self.record = _FakeRecord(rid, confidence)
            self.final_score = final_score

    # A scores higher raw, B scores lower raw but near-certain.
    a = _FakeHit("a", 0.80, 0.5)   # weighted 0.80 * 0.75 = 0.60
    b = _FakeHit("b", 0.79, 0.99)  # weighted 0.79 * 0.995 = 0.786
    assert confidence_weighted_score(0.80, 0.5) == pytest.approx(0.60)
    assert [h.record.id for h in confidence_weighted_sort([a, b])] == ["b", "a"]
    # Clamp: confidence above 1 behaves as 1, below 0 as the floor.
    assert clamp_confidence(1.5) == 0.99
    assert clamp_confidence(-0.5) == 0.05


def test_recall_outcome_endpoint_moves_confidence(client, test_db):
    _setup(test_db)
    id1 = _capture(client, "sess-conf-1", "decision", "Decided to keep Redis for the cache.").json()["id"]
    id2 = _capture(client, "sess-conf-1", "tool_call", "Ran the cache probe; Redis answered.").json()["id"]

    resp = client.post(
        "/v1/capture/recall-outcome",
        json={"memory_ids": [id1, id2, "does-not-exist"], "useful_ids": [id1]},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    by_id = {u["id"]: u for u in body["updated"]}
    assert by_id[id1] == {"id": id1, "before": 0.9, "after": 0.95, "useful": True}, body
    assert by_id[id2] == {"id": id2, "before": 0.9, "after": 0.88, "useful": False}, body
    assert body["skipped"] == [{"id": "does-not-exist", "reason": "not_found"}], body

    row1 = test_db.query(MemoryRecord).filter(MemoryRecord.id == id1).one()
    row2 = test_db.query(MemoryRecord).filter(MemoryRecord.id == id2).one()
    assert row1.confidence == pytest.approx(0.95)
    assert row2.confidence == pytest.approx(0.88)


def test_reinforce_clamps_and_respects_actor_scope(test_db):
    _setup(test_db)
    out = SessionCaptureService.capture_event(
        test_db, actor_name="friday", session_id="sess-conf-2",
        kind="decision", content="Decided to keep Redis for the cache.",
    )
    assert out["stored"] is True, out
    rid = out["id"]

    # Three useful reports: 0.90 -> 0.95 -> 0.99 (clamped, never 1.0).
    for _ in range(3):
        res = reinforce_on_recall(test_db, record_ids=[rid], useful_ids=[rid], actor_name="friday")
        assert res["updated"][0]["id"] == rid, res
    row = test_db.query(MemoryRecord).filter(MemoryRecord.id == rid).one()
    assert row.confidence == pytest.approx(0.99)

    # Another actor cannot move friday's record.
    res = reinforce_on_recall(test_db, record_ids=[rid], useful_ids=[rid], actor_name="someone-else")
    assert res["updated"] == []
    assert res["skipped"] == [{"id": rid, "reason": "not_owned_by_actor"}], res
    row = test_db.query(MemoryRecord).filter(MemoryRecord.id == rid).one()
    assert row.confidence == pytest.approx(0.99)


def test_compress_promotion_bumps_event_confidence(client, test_db):
    _setup(test_db)
    ids = []
    for kind, content in [
        ("decision", "Decided to keep Redis and Qdrant until the ARM server is allocated."),
        ("tool_call", "Ran the fleet health probe; all ten agents returned 200."),
        ("correction", "Owner corrected the plan: latency is not a constraint for Chicago."),
    ]:
        ids.append(_capture(client, "sess-conf-3", kind, content).json()["id"])

    resp = client.post("/v1/capture/compress", json={"session_id": "sess-conf-3"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["compressed"] is True and body["event_count"] == 3, body
    # The promotion gate grants in this test env (same as the MEM-01
    # suite, which asserts the digest lands SEMANTIC); the bump rides
    # on the grant, so assert both together.
    assert body["promoted_to_semantic"] is True, body
    for rid in ids:
        row = test_db.query(MemoryRecord).filter(MemoryRecord.id == rid).one()
        assert row.confidence == pytest.approx(0.93), (rid, row.confidence)


def test_list_actor_sessions_scoped_to_actor(test_db):
    _setup(test_db)
    SessionCaptureService.capture_event(
        test_db, actor_name="friday", session_id="sess-scope-1",
        kind="decision", content="Decided to keep Redis for the cache.",
    )
    sessions = list_actor_sessions(test_db, actor_name="friday")
    assert [s["session_id"] for s in sessions] == ["sess-scope-1"]
    assert sessions[0]["needles"] == {"decision": 1}
    # Another actor sees none of friday's sessions.
    assert list_actor_sessions(test_db, actor_name="someone-else") == []


# ---------------------------------------------------------------------------
# Forge wire: ForgeAdapter records needle-classified observations
# ---------------------------------------------------------------------------


def test_forge_adapter_record_session_observation(client, test_db):
    _setup(test_db)
    forge_adapter = adapter_registry.get_adapter("forge", http_client=client)

    res = forge_adapter.record_session_observation(
        session_id="sess-forge-1",
        content="Decided to keep the async pool at 20 workers for project-alpha.",
        kind="decision",
        project_id="alpha",
    )
    assert res["id"] is not None, res
    row = test_db.query(MemoryRecord).filter(MemoryRecord.id == res["id"]).one()
    assert (row.provenance or {}).get("needle_kind") == "decision"
    assert (row.provenance or {}).get("session_id") == "sess-forge-1"
    assert (row.provenance or {}).get("pattern") == "claude-mem-needles"
    assert "async pool at 20 workers" in row.content_text


def test_forge_adapter_withholds_sensitive_observation(client, test_db):
    _setup(test_db)
    forge_adapter = adapter_registry.get_adapter("forge", http_client=client)

    res = forge_adapter.record_session_observation(
        session_id="sess-forge-2",
        content="This note is confidential, do not share it with anyone.",
        kind="note",
    )
    assert res["id"] is not None, res
    row = test_db.query(MemoryRecord).filter(MemoryRecord.id == res["id"]).one()
    assert (row.provenance or {}).get("needle_kind") == "sensitive"
    assert (row.provenance or {}).get("withheld") is True
    assert "confidential" not in row.content_text
    assert "withheld" in row.content_text
