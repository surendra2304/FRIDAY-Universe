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
