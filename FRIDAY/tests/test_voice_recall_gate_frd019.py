"""TASK-FRD-019: the recall direct-answer gate and 3-letter subjects.

Evidence (FRD-005 re-run #8, run 20261117-055507, production):

- The recall-colour draw fired the FRD-014/017 deterministic direct
  answer: settled reply "Your favorite color is teal." (28 chars),
  brain turn 1.90 s, spoken verbatim.
- The recall-gem draw (the alexandrite fact stored minutes earlier
  by the same call's remember leg; the draw returned 10 hits) did
  NOT produce the gem answer. The settled reply was 75 chars and the
  model spoke a 61-char disclaimer of its own instead; alexandrite
  was never spoken (brain turn 15.69 s).

Root cause, proven three ways (token arithmetic, the brain journal,
and a verbatim simulation of the ranking/gate code): the recall
block's question-word set dropped every token of length <= 3, so
"gem" never became a content word and the question reduced to
{"favorite"}. Three failures compounded: (1) the full-match retry
block (needs >= 2 content words) never ran — the b4 brain journal
holds ONLY the primary-draw line; (2) ranking tied every
favorite-bearing line at overlap 1 and the length tiebreak put the
longest line (the 93-char chai user-model line) on top, not the
30-char alexandrite fact; (3) the gate's all-words-match test passed
trivially on "favorite" alone, so the gate fired with the WRONG
fact — the settled 75-char reply is exactly "Your favorite chai is
masala chai and I review the fleet every morning at 9", the chai
sentence, which the voice model declined to speak as the answer to
a gem question.

Fix pinned here: 3-letter words are content words unless they are
function words, so the subject participates in ranking, retries and
the gate. The gate's unambiguous-only property is unchanged — every
content word must still match the leading hit — and the negative
cases below pin it (absent subject; subject mentioned but no
favorite-fact of that shape).

Leg check (coordinator follow-up, 2026-11-17): the latency-forensics
crew established that the gem turn's 10 hits were the LOCAL leg's
(Memora was stalled ~51 s; the search never reached its access log;
FRIDAY's client waited the full 15 s recall_timeout on the dead
remote leg), while the colour turn's 9 hits came from the REMOTE
leg. The legs are NOT what the gate keys on: _recall_locally's rows
carry the same content_text field the gate reads (plus importance /
final_score / owner_name, which the gate never reads), the recall
block always consumes recall_memories' merged list, and the gate's
ranking/composition inputs are text-only. Fed a merged-shaped hit
set, pristine _dispatch_command reproduces b4's settled reply
exactly; fed the local-leg shape (last test below) it does the
same. The outcome follows the SUBJECT WORD, not the leg: "color"
(5 letters) survived the length filter, "gem" did not. Interaction
with TASK-FRD-020 (PR #864, recall_join_deadline): after it lands, a
stalled-Memora recall returns the local answer in ~5 s instead of
15 s — the gate then composes from local-only hits, so it MUST fire
on them when unambiguous (pinned below); without this fix, #864
would return the wrong (chai) answer faster.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

pytestmark = [pytest.mark.unit]

# The production-shaped hit set (same fixtures as the FRD-014 suite:
# several "favorite"-bearing lines compete with the asked-about fact).
CHAI = "my favorite chai is masala chai and I review the fleet every morning at 9"
ZQ = "my secret favorite number is owner favorite test marker ZQ1794340686"
USERS_CHAI = "User's favorite chai is masala chai."
TEAL_DIRTY = "for me. My favorite color is teal."
TEAL_CLEAN = "my favorite color is teal."
GEM = "My favorite gem is alexandrite."
TEA = "My favorite tea is Assam tea."


def _hits(*texts):
    return [
        {"id": f"hit-{i}", "content_text": t, "memory_type": "episodic"}
        for i, t in enumerate(texts)
    ]


class _FakeMemora:
    def __init__(self, hits):
        self._hits = hits

    def recall_memories(self, agent_name, query, limit=10):
        return list(self._hits)


def _dispatch(monkeypatch, hits, command):
    from friday.api.server import _dispatch_command
    import friday.memory.memora_client as module

    monkeypatch.setattr(module, "memora_client", _FakeMemora(hits))
    return asyncio.run(_dispatch_command(command))


def test_recall_three_letter_subject_gets_the_right_direct_answer(monkeypatch):
    # The re-run #8 shape: the fresh alexandrite record among the
    # favorite-bearing lines. Pre-fix this composed the CHAI answer.
    result = _dispatch(
        monkeypatch,
        _hits(CHAI, ZQ, USERS_CHAI, TEAL_DIRTY, TEAL_CLEAN, GEM),
        "What is my favorite gem?",
    )
    meta = result["metadata"]
    assert meta.get("memory_recall") is True
    assert meta.get("spoken_summary") == "Your favorite gem is alexandrite."
    assert meta.get("fact") == "My favorite gem is alexandrite."
    first_bullet = result["reply"].split("• ")[1]
    assert "alexandrite" in first_bullet


def test_recall_three_letter_subject_second_shape(monkeypatch):
    result = _dispatch(
        monkeypatch,
        _hits(CHAI, ZQ, TEAL_CLEAN, TEA),
        "What is my favorite tea?",
    )
    assert result["metadata"].get("spoken_summary") == (
        "Your favorite tea is Assam tea."
    )


def test_recall_three_letter_subject_retry_block_engages(monkeypatch):
    # With the subject a content word again, the FRD-014/017
    # full-match retry block (needs >= 2 content words) engages for
    # this shape too: a sparse first draw earns the second draw.
    from friday.api.server import _dispatch_command
    import friday.memory.memora_client as module

    class _SparseThenRich:
        def __init__(self):
            self.calls = 0

        def recall_memories(self, agent_name, query, limit=10):
            self.calls += 1
            if self.calls == 1:
                return _hits(CHAI, ZQ)
            return _hits(GEM)

    fake = _SparseThenRich()
    monkeypatch.setattr(module, "memora_client", fake)
    result = asyncio.run(_dispatch_command("What is my favorite gem?"))
    assert fake.calls == 2
    assert result["metadata"].get("spoken_summary") == (
        "Your favorite gem is alexandrite."
    )


def test_recall_colour_shape_unchanged(monkeypatch):
    # The shape that already worked in re-run #8 must keep working
    # byte-for-byte.
    result = _dispatch(
        monkeypatch,
        _hits(CHAI, ZQ, USERS_CHAI, TEAL_DIRTY, TEAL_CLEAN, GEM),
        "What is my favorite color?",
    )
    assert result["metadata"].get("spoken_summary") == (
        "Your favorite color is teal."
    )
    assert result["metadata"].get("fact") == "My favorite color is teal."


def test_recall_absent_subject_stays_a_list(monkeypatch):
    # NEGATIVE: no car fact is stored. The gate must not fire —
    # pre-fix it fired with the chai line, because the 3-letter
    # subject was dropped and "favorite" alone trivially "matched".
    # The honest list/empty reply stands.
    result = _dispatch(
        monkeypatch,
        _hits(CHAI, ZQ, TEAL_DIRTY, TEAL_CLEAN, GEM),
        "What is my favorite car?",
    )
    meta = result["metadata"]
    assert meta.get("memory_recall") is True
    assert "spoken_summary" not in meta
    assert "fact" not in meta


def _local_leg_hits(*texts):
    """Hits in the exact shape _recall_locally returns (the local
    leg of recall_memories): same content_text key, plus the fields
    the gate never reads. Ordered as the local leg orders them —
    its own (final_score, importance) sort puts the two-keyword
    alexandrite fact ahead of the one-keyword chai line."""
    rows = []
    for i, t in enumerate(texts):
        rows.append({
            "id": 1000 + i,
            "content_text": t,
            "memory_type": "episodic",
            "importance": 0.95,
            "created_at": "2026-11-17T00:26:29Z",
            "owner_name": "friday",
            "final_score": 0.22 if "alexandrite" in t else 0.11,
        })
    return rows


def test_recall_gate_fires_on_a_local_leg_only_draw(monkeypatch):
    # The re-run #8 gem turn's actual provenance shape: Memora
    # stalled, the draw is local-leg only. The gate must fire on
    # local-only hits when they are unambiguous — after TASK-FRD-020
    # bounds the remote join, this is the shape a stalled-Memora
    # recall returns. (On pristine main the gate's own re-ranking
    # still tops the chai line and composes it — leg or no leg.)
    result = _dispatch(
        monkeypatch,
        _local_leg_hits(GEM, CHAI, ZQ, TEAL_CLEAN),
        "What is my favorite gem?",
    )
    assert result["metadata"].get("spoken_summary") == (
        "Your favorite gem is alexandrite."
    )
    assert result["metadata"].get("fact") == "My favorite gem is alexandrite."


def test_recall_subject_mentioned_without_a_fact_stays_a_list(monkeypatch):
    # NEGATIVE: a line MENTIONS the subject but is not a favorite-fact
    # of the asked shape. Mentioning is not answering.
    result = _dispatch(
        monkeypatch,
        _hits(CHAI, "the gem collection includes alexandrite and other stones"),
        "What is my favorite gem?",
    )
    meta = result["metadata"]
    assert meta.get("memory_recall") is True
    assert "spoken_summary" not in meta
    assert "fact" not in meta


# ---------------------------------------------------------------------------
# TASK-FRD-022 (PR #865 review follow-up): incidental 3-letter verbs and
# pronouns are function words too. The FRD-019 fix kept every 3-letter
# word that was not already a known function word, so "the gem I saw"
# made "saw" a content word: no stored line contains it, the gate's
# all-words test could never full-match, and the direct answer was
# blocked for such phrasings even though the subject fact was known
# (safe — the wrong fact never fired — but narrower than needed).
# The refinement excludes a small explicit verb/pronoun set while
# keeping every 3-letter subject NOUN (gem, tea, car…) a content word.
# ---------------------------------------------------------------------------

def test_recall_incidental_verb_does_not_block_the_direct_answer(monkeypatch):
    # "…I saw?" — 'saw' rides along; the subject is still 'gem'.
    # On current main this composes NOTHING (saw joins the all-words
    # test and no hit contains it); the fact was known all along.
    result = _dispatch(
        monkeypatch,
        _hits(CHAI, ZQ, USERS_CHAI, TEAL_DIRTY, TEAL_CLEAN, GEM),
        "What is my favorite gem I saw?",
    )
    meta = result["metadata"]
    assert meta.get("memory_recall") is True
    assert meta.get("spoken_summary") == "Your favorite gem is alexandrite."
    assert meta.get("fact") == "My favorite gem is alexandrite."


def test_recall_incidental_verb_got_does_not_block_the_direct_answer(monkeypatch):
    result = _dispatch(
        monkeypatch,
        _hits(CHAI, ZQ, USERS_CHAI, TEAL_DIRTY, TEAL_CLEAN, GEM),
        "What is my favorite gem I got?",
    )
    meta = result["metadata"]
    assert meta.get("spoken_summary") == "Your favorite gem is alexandrite."
    assert meta.get("fact") == "My favorite gem is alexandrite."


@pytest.mark.parametrize("question", [
    "What is my favorite gem?",
    "What is my favorite gem I saw?",
    "What is my favorite gem I got?",
    "What is my favorite gem I see?",
])
def test_recall_wrong_fact_never_composed_for_any_gem_phrasing(
        monkeypatch, question):
    # The FRD-019 defect in its general form: for ANY gem phrasing the
    # composed direct answer is the gem fact or nothing — never the
    # chai sentence. (On pristine main the plain phrasing composes
    # chai verbatim; on current main the incidental phrasings compose
    # nothing. Only the refinement composes alexandrite throughout.)
    result = _dispatch(
        monkeypatch,
        _hits(CHAI, ZQ, USERS_CHAI, TEAL_DIRTY, TEAL_CLEAN, GEM),
        question,
    )
    meta = result["metadata"]
    assert meta.get("spoken_summary") == "Your favorite gem is alexandrite."
    assert meta.get("fact") == "My favorite gem is alexandrite."
    assert "chai" not in str(meta.get("spoken_summary", "")).lower()
    assert "chai" not in str(meta.get("fact", "")).lower()


def test_recall_incidental_phrasing_without_the_fact_stays_a_list(monkeypatch):
    # NEGATIVE: the refinement must not resurrect the wrong-fact fire.
    # With no gem fact stored, an incidental phrasing still earns the
    # honest list — 'gem' remains a content word, so nothing can
    # full-match on "favorite" alone. (On pristine main this fired
    # the chai sentence.)
    result = _dispatch(
        monkeypatch,
        _hits(CHAI, ZQ, TEAL_DIRTY, TEAL_CLEAN, TEA),
        "What is my favorite gem I saw?",
    )
    meta = result["metadata"]
    assert meta.get("memory_recall") is True
    assert "spoken_summary" not in meta
    assert "fact" not in meta
