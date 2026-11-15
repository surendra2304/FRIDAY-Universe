"""TASK-FRD-001: forget-subject resolution must understand natural phrasing.

Production evidence (live conversation audit, 2026-11-15): the owner
stored "test code: FRD001-BETA-9." via chat, then said "Forget the test
code I gave you." 59 seconds later and forget returned not_found —
``_mutation_subject`` kept the conversational frame words {i, gave, you}
and ``_mutation_targets`` requires EVERY subject token to appear
verbatim in the stored fact, which a stored fact can never satisfy for
frame words. These tests pin the fixed behaviour and the safety rails
(ambiguity still refuses; unrelated facts still miss).
"""
from friday.memory.memora_client import MemoraClient


def _hit(text, mid):
    return {"id": mid, "content_text": text}


def test_subject_drops_frame_words_keeps_content():
    assert MemoraClient._mutation_subject("the test code I gave you") == {"test", "code"}


def test_forget_natural_phrasing_matches_stored_fact():
    hits = [_hit("test code: FRD001-BETA-9.", "m1")]
    status, mid, _text, ids = MemoraClient._mutation_targets(
        "the test code I gave you", hits
    )
    assert status == "matched"
    assert mid == "m1"
    assert ids == ["m1"]


def test_forget_told_you_phrasing_matches():
    hits = [_hit("my dentist is Dr Rao", "m2")]
    status, mid, _text, _ids = MemoraClient._mutation_targets(
        "the dentist I told you about", hits
    )
    assert status == "matched"
    assert mid == "m2"


def test_ambiguity_still_needs_clarification():
    hits = [_hit("test code: AAA-1", "m1"), _hit("test code: BBB-2", "m3")]
    status, _mid, _text, _ids = MemoraClient._mutation_targets(
        "the test code I gave you", hits
    )
    assert status == "needs_clarification"


def test_unrelated_fact_still_not_found():
    hits = [_hit("my favorite chai is masala chai", "m4")]
    status, _mid, _text, _ids = MemoraClient._mutation_targets(
        "the test code I gave you", hits
    )
    assert status == "not_found"


def test_exact_wording_still_matches():
    hits = [_hit("my safe word is amber falcon", "m5")]
    status, mid, _text, _ids = MemoraClient._mutation_targets("my safe word", hits)
    assert status == "matched"
    assert mid == "m5"
