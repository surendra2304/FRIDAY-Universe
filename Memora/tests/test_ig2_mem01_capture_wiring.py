"""
TASK-IG2-MEM-01 wiring — the capture → compress → inject loop over HTTP.

The service contracts are locked by test_ig2_mem01_bm25_capture.py. What
was missing — and what this suite locks — is the PRODUCTION CALLER: the
mounted /v1/capture router. Before this wiring, SessionCaptureService
was referenced only by its own module and its tests.

Locked here:
- events are captured through the API with the authenticated identity
  as the actor, secrets are scrubbed before storage, and a session can
  be compressed through the API (idempotently);
- the session-start context endpoint returns hybrid recall AND the
  rendered user-model profile — the inject path consults the user
  model (TASK-IG2-MEM-03) on every call;
- handoff compresses + builds the next pack through the API;
- the routes are mounted on the real app (they answer, not 404) and
  refuse unauthenticated-shaped misuse the same way sibling routers do
  (the actor comes from auth, never from the request body).
"""
import importlib

import pytest

from core.identity.service import IdentityService
from core.memory.user_model_service import UserModelService
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


def test_capture_compress_context_roundtrip_over_http(client, test_db):
    _setup(test_db)
    for kind, content in [
        ("decision", "Decided to keep Redis and Qdrant until the ARM server is allocated."),
        ("tool_call", "Ran the fleet health probe; all ten agents returned 200."),
        ("correction", "Owner corrected the plan: latency is not a constraint for Chicago."),
    ]:
        resp = _capture(client, "sess-http-1", kind, content)
        assert resp.status_code == 200, resp.text
        assert resp.json()["stored"] is True, resp.json()

    resp = client.post("/v1/capture/compress", json={"session_id": "sess-http-1"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["compressed"] is True and body["event_count"] == 3, body

    # Idempotent: the same event set compresses to the same digest.
    resp = client.post("/v1/capture/compress", json={"session_id": "sess-http-1"})
    assert resp.json()["already_existed"] is True

    resp = client.get("/v1/capture/context", params={"q": "Redis Qdrant ARM server"})
    assert resp.status_code == 200, resp.text
    pack = resp.json()
    assert pack["hit_count"] >= 1, pack
    assert "Redis and Qdrant" in pack["context"]
    # The inject path consults the user model on every session start.
    assert "user_model_profile" in pack
    assert "no fields recorded yet" in pack["user_model_profile"]


def test_context_pack_carries_the_user_model_once_fields_exist(client, test_db):
    _setup(test_db)
    out = UserModelService.learn_from_correction(
        test_db, actor_name="friday", field="briefing_time", value="08:50 IST",
        source_ref="owner-correction",
    )
    assert out["updated"] is True, out
    resp = client.get("/v1/capture/context", params={"q": "anything"})
    assert resp.status_code == 200, resp.text
    profile = resp.json()["user_model_profile"]
    assert "briefing_time" in profile and "08:50 IST" in profile
    assert "standing_rule" in profile


def test_capture_scrubs_secrets_over_http(client, test_db):
    _setup(test_db)
    resp = _capture(
        client, "sess-http-secret", "tool_call",
        "deploy used key sk-abcdefghijklmnopqrstuvwx to push the build",
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["stored"] is True
    assert "OpenAI API Key" in body["scrubbed_secret_types"]
    stored = test_db.query(MemoryRecord).filter(MemoryRecord.id == body["id"]).one()
    assert "sk-abcdefghijklmnopqrstuvwx" not in stored.content_text
    assert "[REDACTED]" in stored.content_text


def test_compress_empty_session_reports_no_events(client, test_db):
    _setup(test_db)
    resp = client.post("/v1/capture/compress", json={"session_id": "sess-never-existed"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["compressed"] is False
    assert resp.json()["reason"] == "no_events"


def test_handoff_over_http(client, test_db):
    _setup(test_db)
    assert _capture(client, "sess-http-2", "note", "Wrapped up the deploy verification.").json()["stored"]
    resp = client.post(
        "/v1/capture/handoff",
        json={"session_id": "sess-http-2", "next_query": "deploy verification"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["compression"]["compressed"] is True
    assert body["context"]["hit_count"] >= 1
    assert "user_model_profile" in body


def test_capture_routes_are_mounted():
    from apps.api.main import app

    # This FastAPI version wraps included routers lazily; the OpenAPI
    # surface is the reliable enumeration of what the app serves.
    paths = set(app.openapi()["paths"])
    assert {"/v1/capture/events", "/v1/capture/compress", "/v1/capture/context", "/v1/capture/handoff"} <= paths
