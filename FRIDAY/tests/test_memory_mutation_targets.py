"""WF015 mutation safety: synthetic transports and actual canonical gate AST.

No real memory/network/database. AST extraction executes the production gate
blocks (not a duplicated predicate) without bootstrapping the entire API graph.
"""
from __future__ import annotations

import ast
import copy
import io
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest

from friday.memory.memora_client import MemoraClient

pytestmark = pytest.mark.unit


class Response(io.BytesIO):
    status = 200


def shaped_client():
    c = MemoraClient.__new__(MemoraClient)
    c.remote_enabled = True
    c.base_url = "http://synthetic.invalid"
    c.timeout = 3.5
    c._remote_headers = lambda *a, **k: {}
    c.recall_memories = Mock(return_value=[{"id": "unrelated-synthetic", "content_text": "Synthetic demonstration: the bicycle is orange."}])
    c._mark_record_state = Mock(return_value=True)
    c.record_fact = Mock(return_value={"status": "created", "id": "new-synthetic"})
    return c


def test_forget_unrelated_semantic_hit_must_not_delete(monkeypatch):
    c = shaped_client()
    transport = Mock(return_value=Response(b"{}"))
    monkeypatch.setattr("urllib.request.urlopen", transport)
    result = c.forget_fact("friday", "synthetic deployment marker purple")
    assert result["status"] == "not_found"
    transport.assert_not_called()
    c._mark_record_state.assert_not_called()


def test_correction_unrelated_semantic_hit_must_not_supersede(monkeypatch):
    c = shaped_client()
    transport = Mock()
    monkeypatch.setattr("urllib.request.urlopen", transport)
    result = c.correct_fact("friday", "synthetic deployment marker is purple", "synthetic deployment marker")
    assert result["status"] == "stored_new_only"
    transport.assert_not_called()
    c._mark_record_state.assert_not_called()


@pytest.mark.parametrize("operation", ["forget", "correct"])
def test_multiple_matching_subjects_require_clarification_before_writes(monkeypatch, operation):
    c = shaped_client()
    c.recall_memories.return_value = [
        {"id": "one", "content_text": "My test color is blue."},
        {"id": "two", "content_text": "My test color is orange."},
    ]
    transport = Mock()
    monkeypatch.setattr("urllib.request.urlopen", transport)
    result = c.forget_fact("friday", "test color") if operation == "forget" else c.correct_fact("friday", "my test color is green", "my test color is green")
    assert result["status"] == "needs_clarification"
    transport.assert_not_called()
    c.record_fact.assert_not_called()


def test_matching_subject_not_first_semantic_hit_is_selected(monkeypatch):
    c = shaped_client()
    c.recall_memories.return_value.append({"id": "right", "content_text": "Synthetic deployment marker is purple."})
    requests = []
    def transport(req, **kwargs):
        requests.append(req.full_url)
        return Response(b"{}")
    monkeypatch.setattr("urllib.request.urlopen", transport)
    result = c.forget_fact("friday", "synthetic deployment marker")
    assert result["status"] == "deleted" and result["cloud"] is True
    assert requests == ["http://synthetic.invalid/v1/memories/right?hard=false"]


def test_duplicate_hits_for_same_id_not_false_ambiguity():
    hit = {"id": "one", "content_text": "My test color is blue."}
    assert MemoraClient._mutation_target("test color", [hit, hit]) == ("matched", "one", hit["content_text"])


def test_unknown_delete_never_certified_by_local_mirror(monkeypatch):
    c = shaped_client()
    monkeypatch.setattr("urllib.request.urlopen", Mock(side_effect=TimeoutError("uncertain outcome")))
    result = c.forget_fact("friday", "", memory_id="explicit-synthetic")
    assert result["status"] == "unconfirmed"
    c._mark_record_state.assert_not_called()


@pytest.fixture
def canonical_gate(monkeypatch):
    source = Path(__file__).resolve().parents[1] / "src/friday/api/server.py"
    tree = ast.parse(source.read_text())
    dispatch = next(n for n in tree.body if isinstance(n, ast.AsyncFunctionDef) and n.name == "_dispatch_command")
    blocks = [copy.deepcopy(n) for n in dispatch.body if isinstance(n, ast.If) and isinstance(n.test, ast.Name) and n.test.id in {"_is_forget", "_CORRECTION_TEXT"}]
    assert len(blocks) == 2
    fn = ast.parse("def gate(raw_cmd, _FORGET_QUERY, _is_forget, _CORRECTION_TEXT): pass").body[0]
    fn.body = blocks + [ast.Return(value=ast.Constant(None))]
    module = ast.fix_missing_locations(ast.Module(body=[fn], type_ignores=[]))
    namespace = {"Any": Any, "logger": Mock()}
    exec(compile(module, str(source), "exec"), namespace)
    import friday.memory.memora_client as memory_module
    fake = Mock()
    monkeypatch.setattr(memory_module, "memora_client", fake)
    return namespace["gate"], fake


def test_contextless_forget_that_never_guesses_owner_preference(canonical_gate):
    gate, fake = canonical_gate
    result = gate("forget that", "forget that", True, "")
    assert result["metadata"]["forget_status"] == "needs_clarification"
    assert result["metadata"]["refused"] is True
    fake.forget_fact.assert_not_called()


def test_canonical_unknown_forget_does_not_claim_nothing_happened(canonical_gate):
    gate, fake = canonical_gate
    fake.forget_fact.return_value = {"status": "unconfirmed", "id": "synthetic"}
    result = gate("forget synthetic marker", "synthetic marker", True, "")
    assert "before repeating" in result["reply"]
    assert "nothing was forgotten" not in result["reply"]
    assert result["metadata"]["success"] is False
    assert result["metadata"]["unconfirmed"] is True


@pytest.mark.parametrize("operation", ["forget", "correct"])
def test_canonical_local_scope_is_not_reported_as_shared_success(canonical_gate, operation):
    gate, fake = canonical_gate
    if operation == "forget":
        fake.forget_fact.return_value = {"status": "deleted", "cloud": False}
        result = gate("forget synthetic marker", "synthetic marker", True, "")
    else:
        fake.correct_fact.return_value = {"status": "corrected", "cloud": False}
        result = gate("correction: my marker is green", "", False, "my marker is green")
    assert "local memory backend" in result["reply"]
    assert "not confirmed" in result["reply"]
    assert result["metadata"]["memory_cloud"] is False


def test_canonical_old_winner_is_not_reported_as_replaced(canonical_gate):
    gate, fake = canonical_gate
    fake.correct_fact.return_value = {"status": "not_applied", "winner_id": "old"}
    result = gate("correction: my marker is green", "", False, "my marker is green")
    assert "retained the earlier fact" in result["reply"]
    assert result["metadata"]["success"] is False


def test_canonical_unknown_correction_does_not_assert_unsaved_or_invite_retry(canonical_gate):
    gate, fake = canonical_gate
    fake.correct_fact.return_value = {"status": "unconfirmed", "id": "new"}
    result = gate("correction: my marker is green", "", False, "my marker is green")
    assert "before repeating" in result["reply"]
    assert "NOT saved" not in result["reply"]
    assert result["metadata"]["success"] is False


def test_correction_searches_stable_subject_not_replacement_value(monkeypatch):
    c = shaped_client()
    c.recall_memories.return_value = [{"id": "old", "content_text": "My deployment marker is amber."}]
    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: Response(b'{"status":"superseded","superseded_id":"old","winner_id":"new-synthetic"}'))
    result = c.correct_fact("friday", "my deployment marker is violet", "my deployment marker is violet")
    assert result["status"] == "corrected"
    c.recall_memories.assert_called_once_with("friday", "deployment marker", limit=5)


def test_unspecified_subject_does_not_even_search():
    c = shaped_client()
    assert c.forget_fact("friday", "that")["status"] == "needs_clarification"
    c.recall_memories.assert_not_called()
