"""FRD-017 observability follow-up: every draw in the recall gate
logs one INFO line naming the draw — its query, how many hits it
returned, and how many NEW hits it added to the merged set.

Evidence (FRD-005 re-run #7, production; frd017-forensics): the
recall leg's journal showed only "memory recall: full-match retry
merged 2 hits" twice — the merged TOTAL. That line could not
distinguish "the FRD-017 subject-shaped draw ran and missed" from
"it never ran"; settling which took a full harness reproduction of
the gate. With per-draw lines, the journal alone settles it: a draw
that ran appears with its query and its added count (0 on a miss).

Pinned here:
- one 'memory recall: …' INFO line per recall_memories draw the
  gate makes (primary, concurrent variant, retry draws);
- each retry line keeps the historical prefix
  "memory recall: full-match retry merged {total} hits for {cmd!r}"
  (existing journal greps keep matching) and names the draw query,
  its raw return count, and the NEW hits it added;
- logging only: the gate's answers are unchanged in every shape
  (miss stays honest, landed fact still produces the direct answer).
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

pytestmark = [pytest.mark.unit]

CHAI = "my favorite chai is masala chai and I review the fleet every morning at 9"
ZQ = "my secret favorite number is owner favorite test marker ZQ1794340686"
TEAL_CLEAN = "my favorite color is teal."

SUBJECT_QUERY = "my favorite color"
QUESTION = "What is my favorite color?"


def _hits(*texts):
    return [
        {"id": f"hit-{i}", "content_text": t, "memory_type": "episodic"}
        for i, t in enumerate(texts)
    ]


class _AlwaysSparse:
    """Re-run #7's shape: every draw returns the same sparse
    non-answering set; the fact is never surfaced."""

    def __init__(self):
        self.queries: list[str] = []

    def recall_memories(self, agent_name, query, limit=10):
        self.queries.append(query)
        return _hits(CHAI, ZQ)


class _SubjectLandsTheFact:
    """Only the subject-shaped draw returns the fact."""

    def __init__(self):
        self.queries: list[str] = []

    def recall_memories(self, agent_name, query, limit=10):
        self.queries.append(query)
        if query.strip().lower() == SUBJECT_QUERY:
            return _hits(TEAL_CLEAN)
        return _hits(CHAI, ZQ)


class _DrawLogCapture:
    """Collects the gate's INFO messages straight from its logger
    (friday.api.server), independent of handler/propagation setup."""

    def __init__(self):
        self.messages: list[str] = []
        self._logger = logging.getLogger("friday.api.server")
        self._handler = logging.Handler(level=logging.INFO)
        self._handler.emit = lambda record: self.messages.append(record.getMessage())
        self._old_level = self._logger.level

    def __enter__(self):
        self._logger.addHandler(self._handler)
        self._logger.setLevel(logging.INFO)
        return self

    def __exit__(self, *exc):
        self._logger.removeHandler(self._handler)
        self._logger.setLevel(self._old_level)
        return False

    def draw_lines(self) -> list[str]:
        return [m for m in self.messages if m.startswith("memory recall:")]

    def retry_lines(self) -> list[str]:
        return [m for m in self.messages if "full-match retry merged" in m]


def _run(monkeypatch, fake, command):
    from friday.api.server import _dispatch_command
    import friday.memory.memora_client as module

    monkeypatch.setattr(module, "memora_client", fake)
    with _DrawLogCapture() as cap:
        result = asyncio.run(_dispatch_command(command))
    return result, cap


def test_every_draw_is_named_in_the_journal_on_a_full_miss(monkeypatch):
    # Re-run #7 replay: primary + identical re-draw + subject draw,
    # all landing the same {chai, ZQ} set. The journal must now show
    # one line per draw — including the subject draw by name, with
    # added 0 — which is exactly what re-run #7's journal could not
    # prove.
    fake = _AlwaysSparse()
    result, cap = _run(monkeypatch, fake, QUESTION)

    # One draw line per recall the gate actually made.
    assert len(fake.queries) == 3
    assert len(cap.draw_lines()) == len(fake.queries)

    primary = [m for m in cap.draw_lines() if "primary draw" in m]
    assert len(primary) == 1
    assert QUESTION in primary[0]
    assert "returned 2 hits" in primary[0]

    retries = cap.retry_lines()
    assert len(retries) == 2
    # Historical prefix preserved verbatim (existing greps keep working).
    for line in retries:
        assert line.startswith(
            f"memory recall: full-match retry merged 2 hits for {QUESTION!r}"
        )
        assert "returned 2 hits, added 0 new" in line
    # Each retry draw is named; the subject draw's line is the proof
    # it ran and missed.
    assert QUESTION in retries[0]
    assert SUBJECT_QUERY in retries[1]

    # Behaviour unchanged: a full miss still templates no fact.
    assert "spoken_summary" not in result["metadata"]
    assert "fact" not in result["metadata"]


def test_a_landing_draw_logs_its_added_hit(monkeypatch):
    # The subject draw surfaces the fact: its line must show the raw
    # return and the +1 it added to the merged set, and the gate's
    # answer is the deterministic direct answer, as before.
    fake = _SubjectLandsTheFact()
    result, cap = _run(monkeypatch, fake, QUESTION)

    assert len(cap.draw_lines()) == len(fake.queries)
    subject_lines = [
        m for m in cap.retry_lines() if f"(draw {SUBJECT_QUERY!r}" in m
    ]
    assert len(subject_lines) == 1
    line = subject_lines[0]
    assert line.startswith(
        f"memory recall: full-match retry merged 3 hits for {QUESTION!r}"
    )
    assert "returned 1 hits, added 1 new" in line

    assert result["metadata"].get("spoken_summary") == "Your favorite color is teal."
    assert result["metadata"].get("fact") == TEAL_CLEAN


def test_concurrent_variant_draw_gets_its_own_line(monkeypatch):
    # UK spelling: FRD-016 fires primary + canonical-variant draws
    # concurrently. Both are draws, so both get a line; the retry
    # loop's re-draw and subject draw follow as usual.
    fake = _AlwaysSparse()
    result, cap = _run(monkeypatch, fake, "What is my favourite colour?")

    assert len(fake.queries) == 4
    assert len(cap.draw_lines()) == len(fake.queries)

    variant = [m for m in cap.draw_lines() if "primary variant draw" in m]
    assert len(variant) == 1
    # The variant is the canonicalized (US-spelling) question.
    assert "what is my favorite color?" in variant[0]
    assert "added 0 new hits (merged 2 hits)" in variant[0]

    assert len(cap.retry_lines()) == 2
    assert "spoken_summary" not in result["metadata"]
