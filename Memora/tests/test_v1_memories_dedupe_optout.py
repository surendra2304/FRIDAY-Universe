"""
POST /v1/memories duplicate opt-out is a server decision (follow-up to #831).

PR #831 enforced exact-duplicate dedupe at the service layer, but the
/v1/memories request schema still forwarded a client-supplied
``allow_duplicates`` field verbatim, so any caller could opt out of dedupe
per-request on that endpoint. The fleet census behind this change found
exactly ONE in-repo caller that ever sets the field: FRIDAY's
MemoraClient.correct_fact — an intentional-supersede flow that must mint a
distinct candidate record and then supersedes every old record. These tests
pin the gate that replaced the free choice: the field is honoured only for
server-allowlisted AUTHENTICATED identities (DUPLICATE_OPTOUT_ALLOWED_AGENTS,
today just "friday"); every other caller's opt-out is ignored.

Like test_critical_security_fixes.py, these run against the fail-closed
authentication path (no MEMORA_ALLOW_ANONYMOUS_DEV), because the gate keys on
the authenticated identity — anonymous-dev mode would not exercise it.
"""
import pytest
from fastapi.testclient import TestClient

from core.identity.service import IdentityService
from storage.relational.models import MemoryRecord


FRIDAY_KEY = "friday-optout-key"
INTELX_KEY = "intelx-optout-key"

TEXT = "The deploy freeze lifts on Friday at noon."


@pytest.fixture
def mesh(client: TestClient, test_db, monkeypatch):
    """Two provisioned mesh agents talking to a fail-closed Memora."""
    monkeypatch.delenv("MEMORA_ALLOW_ANONYMOUS_DEV", raising=False)
    monkeypatch.setenv("FRIDAY_API_KEY", FRIDAY_KEY)
    monkeypatch.setenv("INTELX_API_KEY", INTELX_KEY)
    IdentityService.register_agent(test_db, "friday", role="supervisor")
    IdentityService.register_agent(test_db, "intelx", role="worker")
    return {
        "friday": {"X-Agent-Name": "friday", "X-API-Key": FRIDAY_KEY},
        "intelx": {"X-Agent-Name": "intelx", "X-API-Key": INTELX_KEY},
    }


def _all_records(db):
    return (
        db.query(MemoryRecord)
        .order_by(MemoryRecord.created_at.asc(), MemoryRecord.id.asc())
        .all()
    )


def _write(client, headers, **extra):
    payload = {"content_text": TEXT}
    payload.update(extra)
    return client.post("/v1/memories", headers=headers, json=payload)


def test_non_allowlisted_caller_optout_is_ignored(client, mesh, test_db):
    """The headline regression: intelx asks for allow_duplicates=true on a
    repeat write and must still get the canonical record back — no second
    row, is_duplicate=True, same id (PR #831's contract)."""
    first = _write(client, mesh["intelx"])
    assert first.status_code == 201, first.text
    assert first.json()["is_duplicate"] is False

    second = _write(client, mesh["intelx"], allow_duplicates=True)
    assert second.status_code == 201, second.text
    body = second.json()
    assert body["is_duplicate"] is True
    assert body["id"] == first.json()["id"]
    assert len(_all_records(test_db)) == 1


def test_allowlisted_friday_correction_write_stays_distinct(client, mesh, test_db):
    """The one legitimate caller keeps working: FRIDAY's correction flow
    (correct_fact) writes as the authenticated 'friday' identity and must
    mint a distinct candidate record even for byte-identical wording — it
    supersedes the old record itself immediately afterwards."""
    first = _write(client, mesh["friday"])
    assert first.status_code == 201, first.text
    assert first.json()["is_duplicate"] is False

    second = _write(client, mesh["friday"], allow_duplicates=True)
    assert second.status_code == 201, second.text
    body = second.json()
    assert body["is_duplicate"] is False
    assert body["id"] != first.json()["id"]
    assert len(_all_records(test_db)) == 2


def test_ordinary_duplicate_without_flag_still_coalesces(client, mesh, test_db):
    """Baseline unchanged: no flag, no opt-out — for the allowlisted agent
    too, dedupe applies exactly as PR #831 left it."""
    first = _write(client, mesh["friday"])
    assert first.status_code == 201, first.text

    second = _write(client, mesh["friday"])
    assert second.status_code == 201, second.text
    assert second.json()["is_duplicate"] is True
    assert second.json()["id"] == first.json()["id"]
    assert len(_all_records(test_db)) == 1


def test_body_selector_cannot_spoof_allowlisted_identity(client, mesh, test_db):
    """The allowlist keys on the authenticated principal, never the body:
    intelx naming agent_id='friday' in the request body is rejected by
    resolve_agent_selector (403) and writes nothing."""
    resp = _write(client, mesh["intelx"], allow_duplicates=True, agent_id="friday")
    assert resp.status_code == 403, resp.text
    assert len(_all_records(test_db)) == 0
