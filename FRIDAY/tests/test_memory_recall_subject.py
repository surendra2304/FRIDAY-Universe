"""WF015 live regression: conversational wrappers crowded the real subject out.

These are hermetic transport contracts; production corpus/latency evidence is
separate. No test queries or mutates owner records.
"""
from __future__ import annotations

import io
import json
import urllib.parse
from unittest.mock import Mock

import pytest

from friday.memory.memora_client import MemoraClient

pytestmark = pytest.mark.unit


class Response(io.BytesIO):
    status = 200


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(MemoraClient, "_ensure_tables", lambda self: None)
    c = MemoraClient(base_url="http://memora:8000", remote_enabled=True)
    c._recall_locally = Mock(return_value=[{"id": "stale", "content_text": "stale local mirror"}])
    yield c
    c._executor.shutdown(wait=True)


@pytest.mark.parametrize(("question", "subject"), [
    ("do you remember wf015marker", "wf015marker"),
    ("what do you remember about wf015marker", "wf015marker"),
    ("Do you remember my favorite chai?", "my favorite chai"),
    ("what do you know about my travel plan", "my travel plan"),
    ("do you have any memory of the renewal date?", "the renewal date"),
    ("recall my preferred language", "my preferred language"),
    ("my favorite chai", "my favorite chai"),
    ("I remember the blue project", "I remember the blue project"),
    ("the quote says do you remember me", "the quote says do you remember me"),
    ("how to remember CSV quotes", "how to remember CSV quotes"),
])
def test_query_preserves_subject_not_common_question_wrapper(client, monkeypatch, question, subject):
    sent = []
    def transport(req, **kwargs):
        sent.append((urllib.parse.parse_qs(urllib.parse.urlsplit(req.full_url).query)["q"][0], kwargs["timeout"]))
        return Response(json.dumps([{"id": "synthetic", "content_text": "probe note"}]).encode())
    monkeypatch.setattr("urllib.request.urlopen", transport)
    hits = client.recall_memories("friday", question)
    assert hits[0]["id"] == "synthetic"
    assert sent == [(subject, 15.0)]
    assert client.timeout == 3.5  # mutation budget remains unchanged


def test_shared_empty_falls_back_to_local_store_rel005(client, monkeypatch):
    """TASK-REL-005 (2026-11-14) reverses the contract this test used to pin
    ("confirmed shared empty does not resurrect local mirror"). That rule
    caused the production round-trip failure: record_fact writes to the
    local fallback whenever the shared write fails (status "local_only"),
    so the local store is not a mirror of shared records — it is the ONLY
    home of facts FRIDAY just told the owner it saved. A shared empty
    therefore falls back to the local store (whose rows are
    lifecycle-filtered, so locally forgotten facts stay forgotten); only a
    NON-empty shared result remains authoritative (see memora_client)."""
    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: Response(b"[]"))
    hits = client.recall_memories("friday", "local only synthetic marker")
    assert hits[0]["id"] == "stale"
    client._recall_locally.assert_called_once()


def test_unavailable_shared_store_still_has_local_fallback(client, monkeypatch):
    def timeout(*args, **kwargs):
        raise TimeoutError("shared read unavailable")
    monkeypatch.setattr("urllib.request.urlopen", timeout)
    assert client.recall_memories("friday", "my favorite chai")[0]["id"] == "stale"
    client._recall_locally.assert_called_once_with("friday", "my favorite chai", 5)


@pytest.mark.parametrize("body", [{"error": "unavailable"}, ["not a memory row"]])
def test_invalid_remote_schema_not_treated_as_authoritative_empty(client, monkeypatch, body):
    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: Response(json.dumps(body).encode()))
    assert client.recall_memories("friday", "synthetic marker")[0]["id"] == "stale"
    client._recall_locally.assert_called_once()


@pytest.mark.parametrize(("kwargs", "expected"), [
    ({"timeout": 3.5}, 3.5),
    ({"timeout": 0.9}, 0.9),
    ({"timeout": 3.5, "recall_timeout": 12.0}, 12.0),
])
def test_explicit_transport_budget_is_never_silently_overridden(monkeypatch, kwargs, expected):
    monkeypatch.setattr(MemoraClient, "_ensure_tables", lambda self: None)
    seen = []
    def transport(req, **options):
        seen.append(options["timeout"])
        return Response(b"[]")
    monkeypatch.setattr("urllib.request.urlopen", transport)
    c = MemoraClient(base_url="http://memora:8000", remote_enabled=True, **kwargs)
    try:
        assert c.recall_memories("friday", "my subject") == []
        assert seen == [expected]
        assert c.timeout == kwargs["timeout"]
    finally:
        c._executor.shutdown(wait=True)
