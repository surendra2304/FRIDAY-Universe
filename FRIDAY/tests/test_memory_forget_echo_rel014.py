"""TASK-REL-014 (REL-005b): forget-by-subject must not fake ambiguity.

Production evidence (2026-11-14, live probe of the deployed store): the
probe fact 'my safe word is "amber falcon 3"' existed as TWO semantic
records with identical text (created 14:29 and 14:47 during REL-005
verification), and the remember turn's archived dialogue row ranked in the
same recall. ``_mutation_target`` counted records, not facts, so a unique
fact with a duplicate — or a fact shadowed by its own conversation echo —
returned ``needs_clarification`` and could never be forgotten by subject.

These tests pin the resolver contract:
- identical-text duplicates of one fact are ONE target; forget deletes
  EVERY duplicate id (a survivor would resurface as if never forgotten);
- a dialogue echo never competes with a stored fact, even when the echo
  escapes the hygiene noise filter (transcript not led by the user turn,
  or provenance-marked interaction log);
- two DISTINCT stored facts about one subject still clarify;
- a lone echo record remains forgettable (pre-existing behaviour);
- corrections supersede every duplicate of the old fact (local path).
"""
from __future__ import annotations

import io
import json
from unittest.mock import Mock

import pytest

from friday.memory.memora_client import MemoraClient

pytestmark = pytest.mark.unit


class Response(io.BytesIO):
    status = 200


def shaped_client(recall_hits):
    c = MemoraClient.__new__(MemoraClient)
    c.remote_enabled = True
    c.base_url = "http://synthetic.invalid"
    c.timeout = 3.5
    c._remote_headers = lambda *a, **k: {}
    c.recall_memories = Mock(return_value=recall_hits)
    c._mark_record_state = Mock(return_value=True)
    c._local_record_exists = Mock(return_value=True)
    c.record_fact = Mock(return_value={"status": "created", "id": "new-synthetic"})
    return c


FACT = {"id": "fact-1", "content_text": 'my safe word is "amber falcon 3".', "memory_type": "semantic"}
FACT_TWIN = {"id": "fact-2", "content_text": 'my safe word is "amber falcon 3".', "memory_type": "semantic"}
# The archived remember turn (dialogue dump led by the user turn).
ECHO_DUMP = {
    "id": "echo-1",
    "content_text": 'User: remember my safe word is "amber falcon 3" | Assistant: Saved on the local memory backend, Boss.',
    "memory_type": "episodic",
}
# An echo that escapes the hygiene prefix filter: the transcript segment
# does not start with the user turn.
ECHO_OFFSET = {
    "id": "echo-2",
    "content_text": 'Assistant: Done, Boss — saved. | User: my safe word is "amber falcon 3", remember it',
    "memory_type": "episodic",
}
# A provenance-marked interaction log whose text is not transcript-shaped.
ECHO_PROVENANCE = {
    "id": "echo-3",
    "content_text": 'Owner stated the safe word amber falcon 3 during the remember turn',
    "memory_type": "episodic",
    "provenance": {"event_type": "dialogue", "tags": ["dialogue", "turn"]},
}
OTHER_FACT = {"id": "fact-9", "content_text": 'my safe word is "crimson otter 9".', "memory_type": "semantic"}


def test_identical_text_twins_are_one_target():
    status, mid, text, ids = MemoraClient._mutation_targets("safe word", [FACT, FACT_TWIN])
    assert status == "matched"
    assert mid == "fact-1"
    assert sorted(ids) == ["fact-1", "fact-2"]


def test_forget_deletes_every_twin(monkeypatch):
    c = shaped_client([FACT, FACT_TWIN])
    transport = Mock(side_effect=AssertionError("twins are local; no remote DELETE expected"))
    monkeypatch.setattr("urllib.request.urlopen", transport)
    result = c.forget_fact("friday", "my safe word")
    assert result["status"] == "deleted"
    assert result["cloud"] is False
    assert sorted(result["ids"]) == ["fact-1", "fact-2"]
    marked = sorted(call.args[0] for call in c._mark_record_state.call_args_list)
    assert marked == ["fact-1", "fact-2"]


@pytest.mark.parametrize("echo", [ECHO_DUMP, ECHO_OFFSET, ECHO_PROVENANCE])
def test_dialogue_echo_never_competes_with_stored_fact(echo):
    status, mid, _text, ids = MemoraClient._mutation_targets("safe word", [echo, FACT])
    assert status == "matched"
    assert mid == "fact-1"
    assert ids == ["fact-1"]


def test_forget_with_echo_present_deletes_only_the_fact(monkeypatch):
    c = shaped_client([ECHO_OFFSET, FACT])
    monkeypatch.setattr("urllib.request.urlopen", Mock(side_effect=AssertionError("no remote call")))
    result = c.forget_fact("friday", "my safe word")
    assert result["status"] == "deleted"
    assert [call.args[0] for call in c._mark_record_state.call_args_list] == ["fact-1"]


def test_two_distinct_facts_still_clarify():
    status, _mid, _text, ids = MemoraClient._mutation_targets("safe word", [FACT, OTHER_FACT])
    assert status == "needs_clarification"
    assert ids == []


def test_twins_do_not_mask_genuine_ambiguity():
    status, _mid, _text, _ids = MemoraClient._mutation_targets("safe word", [FACT, FACT_TWIN, OTHER_FACT])
    assert status == "needs_clarification"


def test_lone_echo_remains_a_valid_target():
    status, mid, _text, ids = MemoraClient._mutation_targets("safe word", [ECHO_OFFSET])
    assert status == "matched"
    assert mid == "echo-2"
    assert ids == ["echo-2"]


def test_no_candidates_is_not_found():
    status, _mid, _text, _ids = MemoraClient._mutation_targets("safe word", [])
    assert status == "not_found"


def test_mutation_target_compat_shape_with_twins():
    # The 3-tuple legacy shape still resolves twins to a single primary id.
    assert MemoraClient._mutation_target("safe word", [FACT, FACT_TWIN]) == (
        "matched",
        "fact-1",
        FACT["content_text"],
    )


def test_correct_supersedes_every_twin_locally():
    c = shaped_client([FACT, FACT_TWIN])
    c.remote_enabled = False
    c.base_url = ""
    result = c.correct_fact("friday", 'my safe word is "amber falcon 4"', "my safe word")
    assert result["status"] == "corrected"
    assert sorted(result["superseded_ids"]) == ["fact-1", "fact-2"]
    marked = sorted(call.args[0] for call in c._mark_record_state.call_args_list)
    assert marked == ["fact-1", "fact-2"]


def test_remote_forget_deletes_twin_in_shared_store(monkeypatch):
    # Twins held by the shared store: forget must DELETE both ids remotely.
    c = shaped_client([FACT, FACT_TWIN])
    c._local_record_exists = Mock(return_value=False)
    urls = []

    def transport(req, **kwargs):
        urls.append(req.full_url)
        return Response(json.dumps({}).encode())

    monkeypatch.setattr("urllib.request.urlopen", transport)
    result = c.forget_fact("friday", "my safe word")
    assert result["status"] == "deleted"
    assert result["cloud"] is True
    assert sorted(urls) == [
        "http://synthetic.invalid/v1/memories/fact-1?hard=false",
        "http://synthetic.invalid/v1/memories/fact-2?hard=false",
    ]
