"""TASK-MEM-029: production callers for Memora's three shipped-but-never-invoked services.

The Memora side already had the routes mounted and the background pass
running (Memora/tests/test_ig2_mem02_skill_wiring.py,
test_ig2_mem03_user_model_wiring.py, test_ig2_mem01_capture_wiring.py
lock the server-side cycles). What was missing — and what this suite
locks — is the CALLER: FRIDAY's MemoraClient actually invoking them in
production, with the exact payloads the routers expect.

Locked here, against a stub Memora (same pattern as
test_rel031_memora_shared_sync.py — no live server, no real socket):
- skill-learning: record_skill_outcome POSTs /v1/skills/outcomes with
  the router's OutcomeRequest shape; report_task_outcome_async fans
  one task event out to BOTH the old learn-outcome path and the skill
  loop, with the task name as the pattern key and success/failure
  mapped onto the loop's outcome vocabulary;
- user-model: update_user_model_field PUTs /v1/user-model/field and
  record_owner_correction POSTs /v1/user-model/corrections with the
  correction as a standing-rule value; fetch_user_model_render GETs
  /v1/user-model/render and returns "" when nothing is recorded yet
  ("nothing assumed" is never injected into a prompt);
- session capture: record_interaction captures the same turn as a
  /v1/capture/events observation (the choke point — every turn flows
  through record_interaction, so no per-call-site wiring), and
  compress_session POSTs /v1/capture/compress with the process session
  id;
- every new write is fail-soft: a dead Memora is reported in the
  result (stored/updated/compressed False + reason), never raised into
  the caller, and never changes the turn's own record.

The call-site swaps (mixins/tools.py, mixins/fast_paths.py,
cli/main.py, agent.py, api/server.py) are one-line fan-out/hook calls
to these methods; their wiring is verified by reading the diff and by
CI collection of this file.
"""
from __future__ import annotations

import json
import urllib.error
from pathlib import Path

import pytest

from friday.memory.memora_client import MemoraClient


class _Response:
    """Minimal urlopen response (same shape as test_memora_hardening.py)."""

    def __init__(self, status: int, body: dict):
        self.status = status
        self._body = json.dumps(body).encode()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self):
        return self._body


class _StubMemora:
    """Records every request; answers the production response shapes."""

    def __init__(self, monkeypatch, fail_paths=()):
        self.requests: list[dict] = []
        self.fail_paths = set(fail_paths)
        monkeypatch.setattr("urllib.request.urlopen", self._urlopen)

    def _urlopen(self, request, timeout=None):
        method = request.get_method()
        url = request.full_url
        path = url.split("://", 1)[-1].split("/", 1)[-1]
        path = "/" + path.split("?", 1)[0]
        payload = json.loads(request.data.decode()) if request.data else None
        self.requests.append({"method": method, "path": path, "payload": payload, "headers": dict(request.headers)})
        if path in self.fail_paths:
            raise urllib.error.URLError("stub memora down")
        bodies = {
            "/v1/memories/record-interaction": (201, {"status": "success", "recorded_count": 1}),
            "/v1/memories/learn-outcome": (200, {"status": "success", "guidelines": []}),
            "/v1/skills/outcomes": (200, {"stored": True, "id": "rec-skill-1", "pattern_key": "x", "outcome": "success"}),
            "/v1/user-model/field": (200, {"updated": True, "previous_value": None, "version": 1}),
            "/v1/user-model/corrections": (200, {"updated": True, "previous_value": None, "version": 1}),
            "/v1/user-model/render": (200, {"subject": "owner", "profile": "User model — owner:\n- briefing_time: 08:50 IST (preference)"}),
            "/v1/capture/events": (200, {"stored": True, "id": "evt-1"}),
            "/v1/capture/compress": (200, {"compressed": True, "event_count": 1}),
        }
        status, body = bodies.get(path, (404, {}))
        return _Response(status, body)

    def paths(self):
        return [(r["method"], r["path"]) for r in self.requests]

    def payload_for(self, path):
        for r in self.requests:
            if r["path"] == path:
                return r["payload"]
        raise AssertionError(f"no request to {path}; got {self.paths()}")


@pytest.fixture()
def client(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("FRIDAY_API_KEY", "friday-test-key")
    return MemoraClient(
        base_url="http://127.0.0.1:9",
        local_db_path=str(tmp_path / "mem029.db"),
        remote_enabled=True,
    )


@pytest.fixture()
def stub(monkeypatch):
    return _StubMemora(monkeypatch)


def _drain(client):
    client._executor.shutdown(wait=True)


# ----------------------------------------------------------------------
# skill-learning (TASK-IG2-MEM-02)
# ----------------------------------------------------------------------

def test_skill_outcome_posts_router_shape(client, stub):
    result = client.record_skill_outcome(
        "friday",
        pattern_key="morning-fleet-brief",
        outcome="success",
        detail="probe run all agents 200",
    )
    assert result["stored"] is True
    assert ("POST", "/v1/skills/outcomes") in stub.paths()
    payload = stub.payload_for("/v1/skills/outcomes")
    assert payload == {
        "pattern_key": "morning-fleet-brief",
        "outcome": "success",
        "detail": "probe run all agents 200",
    }
    headers = {k.lower(): v for k, v in stub.requests[0]["headers"].items()}
    assert headers["x-agent-name"] == "friday"
    assert headers["authorization"] == "Bearer friday-test-key"


def test_skill_outcome_with_correction_posts_correction_text(client, stub):
    client.record_skill_outcome(
        "friday",
        pattern_key="morning-brief",
        outcome="corrected",
        detail="sent the brief at 09:30",
        correction="Briefs go at 08:50 IST, never 09:30.",
    )
    payload = stub.payload_for("/v1/skills/outcomes")
    assert payload["outcome"] == "corrected"
    assert payload["correction"] == "Briefs go at 08:50 IST, never 09:30."


def test_skill_outcome_failure_is_honest_not_raised(client, monkeypatch):
    stub = _StubMemora(monkeypatch, fail_paths={"/v1/skills/outcomes"})
    result = client.record_skill_outcome(
        "friday", pattern_key="p", outcome="success", detail="d",
    )
    assert result == {"stored": False, "reason": "URLError"}
    assert stub.paths() == [("POST", "/v1/skills/outcomes")]


def test_skill_outcome_remote_disabled_posts_nothing(tmp_path: Path, monkeypatch):
    stub = _StubMemora(monkeypatch)
    client = MemoraClient(
        base_url="http://127.0.0.1:9",
        local_db_path=str(tmp_path / "mem029-off.db"),
        remote_enabled=False,
    )
    result = client.record_skill_outcome(
        "friday", pattern_key="p", outcome="success", detail="d",
    )
    assert result == {"stored": False, "reason": "remote_disabled"}
    assert stub.requests == []


def test_report_task_outcome_fans_out_to_both_paths(client, stub):
    client.report_task_outcome_async(
        "friday",
        "desktop-click",
        "success",
        actions_taken="clicked (10, 20)",
        domain="deterministic_action",
    )
    _drain(client)
    assert ("POST", "/v1/memories/learn-outcome") in stub.paths()
    assert ("POST", "/v1/skills/outcomes") in stub.paths()
    learn = stub.payload_for("/v1/memories/learn-outcome")
    assert learn["task_name"] == "desktop-click" and learn["status"] == "success"
    skill = stub.payload_for("/v1/skills/outcomes")
    assert skill["pattern_key"] == "desktop-click"
    assert skill["outcome"] == "success"
    assert skill["detail"] == "clicked (10, 20)"


def test_report_task_outcome_maps_failure_and_error_detail(client, stub):
    client.report_task_outcome_async(
        "friday",
        "open-browser",
        "failure",
        error_log="timeout after 30s",
        domain="fast_path",
    )
    _drain(client)
    skill = stub.payload_for("/v1/skills/outcomes")
    assert skill["pattern_key"] == "open-browser"
    assert skill["outcome"] == "failure"
    assert skill["detail"] == "timeout after 30s"


# ----------------------------------------------------------------------
# user-model (TASK-IG2-MEM-03)
# ----------------------------------------------------------------------

def test_user_model_field_update_posts_router_shape(client, stub):
    result = client.update_user_model_field(
        "friday",
        field="briefing_time",
        value="08:50 IST",
        kind="preference",
        source_ref="owner-statement",
    )
    assert result["updated"] is True
    assert ("PUT", "/v1/user-model/field") in stub.paths()
    payload = stub.payload_for("/v1/user-model/field")
    assert payload == {
        "field": "briefing_time",
        "value": "08:50 IST",
        "kind": "preference",
        "subject": "owner",
        "confidence": 0.8,
        "source_ref": "owner-statement",
    }


def test_owner_correction_posts_as_standing_rule_value(client, stub):
    result = client.record_owner_correction(
        "friday",
        field="owner_correction",
        value="Briefs go at 08:50 IST, never 09:30.",
        source_ref="owner-correction:memory-fast-path",
    )
    assert result["updated"] is True
    assert ("POST", "/v1/user-model/corrections") in stub.paths()
    payload = stub.payload_for("/v1/user-model/corrections")
    assert payload == {
        "field": "owner_correction",
        "value": "Briefs go at 08:50 IST, never 09:30.",
        "subject": "owner",
        "source_ref": "owner-correction:memory-fast-path",
    }


def test_user_model_write_failure_is_honest(client, monkeypatch):
    stub = _StubMemora(monkeypatch, fail_paths={"/v1/user-model/corrections"})
    result = client.record_owner_correction(
        "friday", field="owner_correction", value="x",
    )
    assert result == {"updated": False, "reason": "URLError"}
    assert stub.paths() == [("POST", "/v1/user-model/corrections")]


def test_fetch_user_model_render_returns_profile(client, stub):
    profile = client.fetch_user_model_render("friday")
    assert ("GET", "/v1/user-model/render") in stub.paths()
    assert "briefing_time: 08:50 IST" in profile


def test_fetch_user_model_render_empty_when_nothing_assumed(client, monkeypatch):
    def _empty(request, timeout=None):
        return _Response(200, {"subject": "owner", "profile": "User model — owner: (no fields recorded yet — nothing assumed)"})

    monkeypatch.setattr("urllib.request.urlopen", _empty)
    assert client.fetch_user_model_render("friday") == ""


def test_fetch_user_model_render_empty_when_remote_disabled(tmp_path: Path, monkeypatch):
    _StubMemora(monkeypatch)
    client = MemoraClient(
        base_url="http://127.0.0.1:9",
        local_db_path=str(tmp_path / "mem029-off2.db"),
        remote_enabled=False,
    )
    assert client.fetch_user_model_render("friday") == ""


# ----------------------------------------------------------------------
# session capture (TASK-IG2-MEM-01, PR #709)
# ----------------------------------------------------------------------

def test_session_id_is_process_stable_and_prefixed(client):
    assert client.session_id.startswith("friday-")
    assert client.session_id == client.session_id


def test_capture_event_posts_router_shape(client, stub):
    result = client.capture_session_event(
        "friday",
        session_id="sess-9",
        kind="decision",
        content="Decided to keep Redis and Qdrant.",
    )
    assert result["stored"] is True
    payload = stub.payload_for("/v1/capture/events")
    assert payload == {
        "session_id": "sess-9",
        "kind": "decision",
        "content": "Decided to keep Redis and Qdrant.",
    }


def test_capture_event_defaults_to_process_session_id(client, stub):
    client.capture_session_event("friday", content="hello")
    payload = stub.payload_for("/v1/capture/events")
    assert payload["session_id"] == client.session_id
    assert payload["kind"] == "observation"


def test_record_interaction_also_captures_the_turn(client, stub):
    result = client.record_interaction("friday", "open the browser", "done, Boss")
    assert result["status"] == "success"
    assert ("POST", "/v1/memories/record-interaction") in stub.paths()
    assert ("POST", "/v1/capture/events") in stub.paths()
    payload = stub.payload_for("/v1/capture/events")
    assert payload["session_id"] == client.session_id
    assert payload["kind"] == "observation"
    assert "User: open the browser" in payload["content"]
    assert "FRIDAY: done, Boss" in payload["content"]


def test_record_interaction_capture_miss_does_not_change_result(client, monkeypatch):
    stub = _StubMemora(monkeypatch, fail_paths={"/v1/capture/events"})
    result = client.record_interaction("friday", "open the browser", "done, Boss")
    assert result["status"] == "success"
    assert ("POST", "/v1/capture/events") in stub.paths()


def test_record_interaction_captures_even_when_record_fails(client, monkeypatch):
    stub = _StubMemora(monkeypatch, fail_paths={"/v1/memories/record-interaction"})
    result = client.record_interaction("friday", "open the browser", "done, Boss")
    assert result["cloud"] is False
    assert ("POST", "/v1/capture/events") in stub.paths()


def test_compress_session_posts_process_session_id(client, stub):
    result = client.compress_session("friday")
    assert result["compressed"] is True
    payload = stub.payload_for("/v1/capture/compress")
    assert payload == {"session_id": client.session_id}


def test_compress_session_failure_is_honest(client, monkeypatch):
    stub = _StubMemora(monkeypatch, fail_paths={"/v1/capture/compress"})
    result = client.compress_session("friday")
    assert result == {"compressed": False, "reason": "URLError"}
    assert stub.paths() == [("POST", "/v1/capture/compress")]


def test_async_variants_submit_all_four_writes(client, stub):
    client.record_skill_outcome_async("friday", pattern_key="p", outcome="success", detail="d")
    client.update_user_model_field_async("friday", field="f", value="v", kind="preference")
    client.record_owner_correction_async("friday", field="owner_correction", value="c")
    client.capture_session_event_async("friday", content="e")
    _drain(client)
    assert ("POST", "/v1/skills/outcomes") in stub.paths()
    assert ("PUT", "/v1/user-model/field") in stub.paths()
    assert ("POST", "/v1/user-model/corrections") in stub.paths()
    assert ("POST", "/v1/capture/events") in stub.paths()
