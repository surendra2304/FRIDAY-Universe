"""TASK-FRD-017: the recall gate must reach the deterministic direct
answer on the full-match RETRY path, not only on the primary draw.

Evidence (FRD-005 re-run #6, run 20261116-200627, production):

- The recall leg ("What is my favorite color?") took a 53.59 s brain
  turn and the participant heard ZERO non-silent audio in the 60 s
  window. The brain journal logged "memory recall: full-match retry
  merged 2 hits" and the settled reply was 205 chars — the exact
  length FRD-014 proved is the gate's header + chai bullet + ZQ-marker
  bullet with NO teal record in the presentable set.
- Root cause: the FRD-014 retry's draws are the spelling variant and
  an IDENTICAL re-draw of the question-shaped query. Under Memora
  hybrid-search sparsity both landed the same non-answering set, so
  no hit matched every question content word, the deterministic
  composition never fired, metadata carried no spoken_summary/fact,
  the bridge's recall fact guard had nothing to template from, and
  the realtime model was left to compose the spoken answer from the
  bullet list (and, via the delivery watch, improvised one — the
  separate FRD-018 defect).
- Fix pinned here: after the variant + original-query draws, the
  retry makes ONE final subject-shaped draw ("my favorite color" —
  the stored fact's own phrasing, the FRD-001 probe idiom), merged
  with the same dedupe + filter. A landed fact then produces
  metadata.spoken_summary + metadata.fact exactly as on the primary
  path. A continued miss still templates NOTHING — no fact is ever
  composed from a non-matching line (FRD-014's pinned honesty).
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

pytestmark = [pytest.mark.unit]

# The production-shaped hit set (FRD-014 constants, measured live on
# S1): favorite-bearing lines that do NOT answer the color question.
CHAI = "my favorite chai is masala chai and I review the fleet every morning at 9"
ZQ = "my secret favorite number is owner favorite test marker ZQ1794340686"
TEAL_CLEAN = "my favorite color is teal."
TEAL_UK = "My favourite colour is teal."

SUBJECT_QUERY = "my favorite color"


def _hits(*texts):
    return [
        {"id": f"hit-{i}", "content_text": t, "memory_type": "episodic"}
        for i, t in enumerate(texts)
    ]


class _SparseQuestionDraws:
    """Re-run #6's draw behaviour: every QUESTION-shaped draw (primary,
    spelling variant, identical re-draw) returns the same sparse
    non-answering set; only the subject-shaped draw returns the fact —
    the fact was in the store the whole time, the question-shaped
    retrieval never surfaced it."""

    def __init__(self, fact_text):
        self._fact_text = fact_text
        self.queries: list[str] = []

    def recall_memories(self, agent_name, query, limit=10):
        self.queries.append(query)
        if query.strip().lower() == SUBJECT_QUERY:
            return _hits(self._fact_text)
        return _hits(CHAI, ZQ)


class _AlwaysSparse:
    """Every draw — question-shaped and subject-shaped alike — returns
    only the non-answering set (the fact is genuinely not retrievable
    this turn)."""

    def __init__(self):
        self.queries: list[str] = []

    def recall_memories(self, agent_name, query, limit=10):
        self.queries.append(query)
        return _hits(CHAI, ZQ)


def _run(monkeypatch, fake, command):
    from friday.api.server import _dispatch_command
    import friday.memory.memora_client as module

    monkeypatch.setattr(module, "memora_client", fake)
    return asyncio.run(_dispatch_command(command))


def test_subject_draw_recovers_the_fact_the_question_draws_missed(monkeypatch):
    # The re-run #6 production shape, US spelling: primary + identical
    # re-draw both land {chai, ZQ}; only the subject-shaped draw can
    # surface the fact. On pre-FRD-017 code the subject draw is never
    # issued, so spoken_summary/fact are absent and this test fails.
    fake = _SparseQuestionDraws(TEAL_CLEAN)
    result = _run(monkeypatch, fake, "What is my favorite color?")
    meta = result["metadata"]
    assert meta.get("memory_recall") is True
    # The subject-shaped draw was actually issued, after the
    # question-shaped draws missed.
    assert SUBJECT_QUERY in fake.queries
    # The deterministic direct answer is emitted on the retry path
    # exactly as on the primary path (FRD-014 contract).
    assert meta.get("spoken_summary") == "Your favorite color is teal."
    assert meta.get("fact") == TEAL_CLEAN
    # And the text reply now leads with the asked-about fact.
    first_bullet = result["reply"].split("• ")[1]
    assert "teal" in first_bullet


def test_subject_draw_recovers_across_the_variant_path(monkeypatch):
    # UK spelling: FRD-016 fires the primary + canonical-variant draws
    # concurrently and the retry re-draws the original — all sparse.
    # The subject draw (built from canonicalized content words) still
    # lands the fact, and the spoken form keeps the fact's own
    # spelling (FRD-014: matching is canonicalized, speech is not).
    fake = _SparseQuestionDraws(TEAL_UK)
    result = _run(monkeypatch, fake, "What is my favourite colour?")
    meta = result["metadata"]
    assert meta.get("memory_recall") is True
    assert SUBJECT_QUERY in fake.queries
    assert meta.get("spoken_summary") == "Your favourite colour is teal."
    assert meta.get("fact") == TEAL_UK


def test_no_fact_is_templated_when_every_draw_misses(monkeypatch):
    # Honesty guard for the extended chain: the subject draw runs, but
    # when NO draw surfaces a hit matching every question content
    # word, the gate must still emit no spoken_summary and no fact —
    # a direct answer is never composed from a non-matching line.
    fake = _AlwaysSparse()
    result = _run(monkeypatch, fake, "What is my favorite color?")
    meta = result["metadata"]
    assert meta.get("memory_recall") is True
    assert SUBJECT_QUERY in fake.queries  # the extended chain did run
    assert "spoken_summary" not in meta
    assert "fact" not in meta
    assert "holding onto" in result["reply"]
