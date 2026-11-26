"""TASK-IG-VOI-04 — the voice surface contract.

Source idea: reel Da6PwA8z-wq (AURA, a designed assistant front-end
over a live voice pipeline). The deliverable is the contract in
FRIDAY/docs/VOICE_SURFACE_CONTRACT.md plus the additive `voice` and
`language` fields in the worker's status file, so any surface the
owner picks (Halo today, a stored candidate tomorrow) binds to the
same truth.

These tests pin the contract from both sides:
- the document names every always-present status key, every worker
  state, and the speed rules;
- the worker's _write_status actually emits those keys, JSON-clean,
  with the configured voice and language riding along.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

FRIDAY_ROOT = Path(__file__).resolve().parents[1]
CONTRACT = FRIDAY_ROOT / "docs" / "VOICE_SURFACE_CONTRACT.md"

ALWAYS_KEYS = {
    "state", "provider", "model", "voice", "language",
    "detail", "pid", "updated_at",
}
WORKER_STATES = {
    "registered", "job-received", "ready", "recovering",
    "degraded", "unavailable", "closed",
}


def test_contract_document_covers_the_schema_and_states():
    text = CONTRACT.read_text(encoding="utf-8")
    for key in ALWAYS_KEYS | {"room", "job_id"}:
        assert f"`{key}`" in text, key
    for state in WORKER_STATES:
        assert f"`{state}`" in text, state


def test_contract_document_states_the_speed_and_honesty_rules():
    text = CONTRACT.read_text(encoding="utf-8")
    assert "8s" in text and "4–6s" in text  # FRD-005 thresholds
    assert "never invented" in text  # diagnostics doctrine
    assert "confirmation_required" in text  # TASK-IG-VOI-01 surface duty
    assert "additive-only" in text  # change discipline


@pytest.fixture()
def worker_with_tmp_status(tmp_path, monkeypatch):
    pytest.importorskip("livekit.agents")
    from friday.voice import livekit_worker as worker

    status = tmp_path / "voice_worker_status.json"
    monkeypatch.setattr(worker, "STATUS_FILE", status)
    return worker, status


def test_status_write_emits_the_contract_keys(worker_with_tmp_status, monkeypatch):
    worker, status = worker_with_tmp_status
    monkeypatch.delenv("FRIDAY_VOICE_LANGUAGE", raising=False)
    worker._write_status("ready", "gemini-realtime", model="gemini-3.8-live",
                         room="friday-voice", job_id="job-1")
    payload = json.loads(status.read_text(encoding="utf-8"))
    assert ALWAYS_KEYS <= set(payload)
    assert payload["state"] == "ready"
    assert payload["provider"] == "gemini-realtime"
    assert payload["voice"] == worker._voice_name()
    # TASK-VOI-042: unconfigured now reports the pinned default
    # en-IN — the status file must show the language the session
    # actually runs, never an empty "mirroring".
    assert payload["language"] == "en-IN"
    assert payload["room"] == "friday-voice"
    assert payload["job_id"] == "job-1"


def test_status_write_carries_the_language_profile(worker_with_tmp_status, monkeypatch):
    worker, status = worker_with_tmp_status
    monkeypatch.setenv("FRIDAY_VOICE_LANGUAGE", "te-IN")
    worker._write_status("registered", "pending")
    payload = json.loads(status.read_text(encoding="utf-8"))
    assert payload["language"] == "te-IN"


def test_status_write_never_raises_into_the_worker(worker_with_tmp_status, monkeypatch):
    worker, status = worker_with_tmp_status
    monkeypatch.setattr(worker, "STATUS_FILE", status / "missing-dir" / "x.json")
    # A broken status path must degrade to a warning, never an exception.
    worker._write_status("ready", "gemini-realtime")
