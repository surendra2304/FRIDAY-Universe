"""WF-015: real urllib response and deployed Memora receipt contracts.

Transport is hermetic here; production evidence is recorded separately. A real
urllib HTTPResponse has .status, NOT the requests/httpx .status_code property.
"""
from __future__ import annotations

import io
import json
from http.client import HTTPResponse
from unittest.mock import Mock

import pytest

from friday.memory.memora_client import MemoraClient

pytestmark = pytest.mark.unit


class Socket:
    def __init__(self, body: dict):
        encoded = json.dumps(body).encode()
        self.data = io.BytesIO(b"HTTP/1.1 200 OK\r\nContent-Length: " + str(len(encoded)).encode() + b"\r\n\r\n" + encoded)

    def makefile(self, *args, **kwargs):
        return self.data


def response(body: dict) -> HTTPResponse:
    result = HTTPResponse(Socket(body))
    result.begin()
    return result


@pytest.fixture
def client(monkeypatch):
    # No local store/network during constructor; all effects asserted below.
    monkeypatch.setattr(MemoraClient, "_ensure_tables", lambda self: None)
    c = MemoraClient(base_url="http://memora:8000", remote_enabled=True)
    c.recall_memories = Mock(return_value=[{"id": "old", "content_text": "my test color is blue"}])
    c.record_fact = Mock(return_value={"id": "new", "storage_durable": True, "lifecycle_state": "active"})
    c._mark_record_state = Mock(return_value=False)
    yield c
    c._executor.shutdown(wait=True)


def test_http_response_has_status_not_status_code():
    with response({}) as resp:
        assert resp.status == 200
        assert not hasattr(resp, "status_code")


def test_deployed_write_receipt_without_status_can_be_corrected(client, monkeypatch):
    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: response({"status": "superseded", "superseded_id": "old", "winner_id": "new"}))
    result = client.correct_fact("friday", "my test color is green", "test color")
    assert result["status"] == "corrected"
    assert result["winner_id"] == "new"
    assert result["cloud"] is True
    client._mark_record_state.assert_not_called()
    assert client.record_fact.call_args.kwargs["allow_duplicates"] is True


def test_real_urllib_status_used_after_legacy_status_receipt(client, monkeypatch):
    client.record_fact.return_value = {"status": "created", "id": "new"}
    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: response({"status": "superseded", "superseded_id": "old", "winner_id": "new"}))
    assert client.correct_fact("friday", "my test color is green", "test color")["status"] == "corrected"
    client._mark_record_state.assert_not_called()


@pytest.mark.parametrize("stored", [{}, {"status": "error", "id": "new"}, {"status": "disabled"}, {"id": "new", "storage_durable": False}])
def test_missing_failed_or_nondurable_receipt_never_corrected(client, monkeypatch, stored):
    client.record_fact.return_value = stored
    transport = Mock()
    monkeypatch.setattr("urllib.request.urlopen", transport)
    result = client.correct_fact("friday", "my test color is green", "test color")
    assert result["status"] == "error"
    transport.assert_not_called()
    client._mark_record_state.assert_not_called()


def test_same_id_dedup_cannot_supersede_itself(client, monkeypatch):
    client.record_fact.return_value = {"id": "old", "is_duplicate": True}
    transport = Mock()
    monkeypatch.setattr("urllib.request.urlopen", transport)
    result = client.correct_fact("friday", "my test color is green", "test color")
    assert result["status"] != "corrected"
    transport.assert_not_called()
    client._mark_record_state.assert_not_called()


def test_service_may_keep_old_fact_as_winner(client, monkeypatch):
    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: response({"status": "superseded", "superseded_id": "new", "winner_id": "old"}))
    result = client.correct_fact("friday", "my test color is green", "test color")
    assert result["status"] == "not_applied"
    assert result["winner_id"] == "old"
    assert result["superseded_id"] == "new"
    client._mark_record_state.assert_not_called()


def test_unknown_remote_outcome_never_guesses_from_http_200(client, monkeypatch):
    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: response({"status": "superseded"}))
    result = client.correct_fact("friday", "my test color is green", "test color")
    assert result["status"] == "unconfirmed"
    client._mark_record_state.assert_not_called()


@pytest.mark.parametrize("allow", [False, True])
def test_record_fact_only_bypasses_dedup_when_explicit(client, monkeypatch, allow):
    seen = []
    def transport(req, **kwargs):
        seen.append(json.loads(req.data))
        return response({"id": "new", "storage_durable": True})
    monkeypatch.setattr("urllib.request.urlopen", transport)
    # Exercise real implementation, not the fixture's correction stub.
    result = MemoraClient.record_fact(client, "friday", "disposable test note", allow_duplicates=allow)
    assert result["id"] == "new"
    assert seen[0].get("allow_duplicates", False) is allow
    assert seen[0]["memory_type"] == "episodic"


def test_uncertain_remote_supersession_cannot_be_certified_by_local_mirror(client, monkeypatch):
    client._mark_record_state.return_value = True
    def timeout(*args, **kwargs):
        raise TimeoutError("uncertain mutation")
    monkeypatch.setattr("urllib.request.urlopen", timeout)
    result = client.correct_fact("friday", "my test color is green", "test color")
    assert result["status"] == "unconfirmed"
    assert result["id"] == "new"
    client._mark_record_state.assert_not_called()


def test_local_only_candidate_never_submitted_to_shared_supersede(client, monkeypatch):
    client.record_fact.return_value = {"id": "new", "status": "local_only", "cloud": False}
    client._mark_record_state.return_value = True
    transport = Mock()
    monkeypatch.setattr("urllib.request.urlopen", transport)
    result = client.correct_fact("friday", "my test color is green", "test color")
    assert result["status"] == "corrected"
    assert result["cloud"] is False
    transport.assert_not_called()


def test_new_only_receipt_retains_shared_storage_scope(client):
    client.recall_memories.return_value = []
    result = client.correct_fact("friday", "my test color is green", "test color")
    assert result["status"] == "stored_new_only"
    assert result["cloud"] is True
