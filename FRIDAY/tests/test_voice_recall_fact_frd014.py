"""TASK-FRD-014: D10 — the spoken recall answer must carry the fact.

Evidence (FRD-005 re-run #4, run 20261116-150642, production journals):

- The recall leg's bridge turn b3-e2a326 answered in 16.61 s and the
  spoken answer was "I have your favorite color safely recorded in my
  memory." — the recalled fact ('teal') was never stated. The brain's
  deterministic recall gate returned a header + bullet dump with NO
  spoken_summary, so the voice bridge handed the realtime model the
  whole list and the model paraphrased it into a storage
  confirmation.
- The gate's ranking had a deterministic bug: question tokens kept
  their punctuation ("color?"), so the subject word never matched any
  stored line; ranking degenerated to (personal, length) among every
  "favorite"-bearing line. Proven live 2026-11-16: "What is my
  favorite color?" returned the teal fact LAST and cut its clean
  duplicate below the 4-line cap.
- The delivery watch then nudged via generate_reply(user_input=
  "tell Surendra the outcome…"), so the model improvised a NEW
  answer — also without 'teal' — whose ~20 s generation landed after
  the participant disconnected.

Fixes pinned here: punctuation-stripped question tokens; a direct
spoken answer (metadata.spoken_summary + metadata.fact) when the
leading hit matches every question content word; a bridge-side
recall fact guard that templates the spoken_reply from the fact
when the value tokens are missing; the remember gate's residue
regex accepting a sentence-final period ("for me. My favorite…");
and verbatim delivery in the worker's delivery watch (repeat-
verbatim instruction, tools off) instead of a retelling prompt.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

pytestmark = [pytest.mark.unit]

# The production-shaped hit set (search return order as measured live
# on S1, 2026-11-16): several "favorite"-bearing lines compete with
# the asked-about fact.
CHAI = "my favorite chai is masala chai and I review the fleet every morning at 9"
ZQ = "my secret favorite number is owner favorite test marker ZQ1794340686"
USERS_CHAI = "User's favorite chai is masala chai."
TEAL_DIRTY = "for me. My favorite color is teal."
TEAL_CLEAN = "my favorite color is teal."
STAR = "my favourite star is called FRD012PROBE."


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


# ---------------------------------------------------------------------------
# Brain side: the recall gate composes a direct spoken answer
# ---------------------------------------------------------------------------

def test_recall_specific_question_gets_direct_spoken_answer(monkeypatch):
    result = _dispatch(
        monkeypatch,
        _hits(CHAI, ZQ, USERS_CHAI, TEAL_DIRTY, TEAL_CLEAN),
        "What is my favorite color?",
    )
    meta = result["metadata"]
    assert meta.get("memory_recall") is True
    # The spoken form IS the answer, carrying the fact verbatim.
    assert meta.get("spoken_summary") == "Your favorite color is teal."
    assert meta.get("fact") == "My favorite color is teal."
    # The text reply still lists the memories — and now leads with the
    # asked-about fact instead of burying it.
    first_bullet = result["reply"].split("• ")[1]
    assert "teal" in first_bullet


def test_recall_ranking_no_longer_degenerates_on_punctuation(monkeypatch):
    # Pre-fix shape: with the subject word unmatchable ("color?"), the
    # clean teal record ranked by length among the favorite lines and
    # landed LAST of the four shown. Post-fix it must lead.
    result = _dispatch(
        monkeypatch,
        _hits(CHAI, ZQ, USERS_CHAI, STAR, TEAL_CLEAN),
        "What is my favorite color?",
    )
    first_bullet = result["reply"].split("• ")[1]
    assert "teal" in first_bullet
    assert result["metadata"].get("spoken_summary") == "Your favorite color is teal."


def test_recall_spelling_variant_retry_recovers_a_missed_fact(monkeypatch):
    # Live shape (2026-11-16): the British query's search returned a
    # sparse set with NO teal record at all; the US-spelled query
    # returns it. When no presentable hit matches every content word,
    # the gate retries once with the canonicalized variant and merges.
    from friday.api.server import _dispatch_command
    import friday.memory.memora_client as module

    class _VariantMemora:
        def recall_memories(self, agent_name, query, limit=10):
            if "favourite" in query:
                return _hits(CHAI, ZQ)  # sparse miss set
            return _hits(TEAL_CLEAN)    # canonicalized variant finds it

    monkeypatch.setattr(module, "memora_client", _VariantMemora())
    result = asyncio.run(_dispatch_command("What is my favourite colour?"))
    assert result["metadata"].get("spoken_summary") == (
        "Your favorite color is teal."
    )
    assert "teal" in result["reply"]


def test_recall_browsing_question_keeps_the_list(monkeypatch):
    result = _dispatch(
        monkeypatch,
        _hits(CHAI, TEAL_CLEAN),
        "What do you remember about me?",
    )
    meta = result["metadata"]
    assert meta.get("memory_recall") is True
    # No content words survive the stopwords for a browsing question,
    # so there is no single direct answer to template — the list stays
    # the spoken form too.
    assert "spoken_summary" not in meta
    assert "fact" not in meta
    assert "holding onto" in result["reply"]


def test_recall_without_a_full_subject_match_stays_a_list(monkeypatch):
    # The re-run #4 hit-set shape: the search returned only
    # favorite-bearing lines that do NOT answer the question. No
    # direct answer may be templated from a non-matching line.
    result = _dispatch(
        monkeypatch,
        _hits(CHAI, ZQ),
        "What is my favorite color?",
    )
    meta = result["metadata"]
    assert meta.get("memory_recall") is True
    assert "spoken_summary" not in meta
    assert "fact" not in meta


def test_recall_marker_style_question(monkeypatch):
    result = _dispatch(
        monkeypatch,
        _hits(CHAI, "my favourite constellation is called FRD014PROBE.", TEAL_CLEAN),
        "What is my favourite constellation called?",
    )
    assert result["metadata"].get("spoken_summary") == (
        "Your favourite constellation is called FRD014PROBE."
    )


def test_recall_matches_across_spelling_variants(monkeypatch):
    # Drill finding (staging brain vs the production store): the same
    # fact exists in both spellings from different sessions. A British
    # question must still match the US-spelled fact (and outrank a
    # British decoy that matches only one content word) — matching is
    # canonicalized, the spoken form keeps the fact's own spelling.
    result = _dispatch(
        monkeypatch,
        _hits("my favourite constellation is called FRD014PROBE.", TEAL_CLEAN),
        "What is my favourite colour?",
    )
    assert result["metadata"].get("spoken_summary") == (
        "Your favorite color is teal."
    )
    result = _dispatch(
        monkeypatch,
        _hits(CHAI, "My favourite colour is teal."),
        "What is my favorite color?",
    )
    assert result["metadata"].get("spoken_summary") == (
        "Your favourite colour is teal."
    )


# ---------------------------------------------------------------------------
# Brain side: the remember gate no longer stores the "for me." residue
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("message,expected_fact", [
    ("remember this for me. My favorite color is teal.",
     "My favorite color is teal."),
    ("Please remember this for me. My favorite color is teal.",
     "My favorite color is teal."),
    ("remember this for me: my test phrase is \"crimson tiger 7\"",
     "my test phrase is \"crimson tiger 7\""),
])
def test_remember_for_me_residue(message, expected_fact, monkeypatch):
    from friday.api.server import _dispatch_command
    from friday.memory.memora_client import memora_client

    captured = {}

    def fake_record_fact(**kwargs):
        captured.update(kwargs)
        return {"status": "success", "id": "fixture"}

    monkeypatch.setattr(memora_client, "record_fact", fake_record_fact)
    result = asyncio.run(_dispatch_command(message))
    assert result["metadata"]["memory_store"] is True
    assert captured["fact_text"] == expected_fact


# ---------------------------------------------------------------------------
# Bridge side: the recall fact guard
# ---------------------------------------------------------------------------

def test_fact_value_tokens_pick_the_value():
    from friday.voice.brain_bridge import _fact_value_tokens

    assert _fact_value_tokens("my favorite color is teal.") == ["teal"]
    assert _fact_value_tokens(
        "my favourite constellation is called FRD014PROBE."
    ) == ["frd014probe"]
    assert _fact_value_tokens("User's favorite chai is masala chai.") == [
        "masala", "chai",
    ]


def test_guard_replaces_a_factless_spoken_reply():
    from friday.voice.brain_bridge import _recall_fact_guard

    meta = {"memory_recall": True, "fact": "my favorite color is teal."}
    dump = (
        "Of course I remember, Boss. Here's what I'm holding onto:\n\n"
        f"• {CHAI}\n• {ZQ}"
    )
    assert _recall_fact_guard(meta, "answered", dump) == (
        "Your favorite color is teal."
    )


def test_guard_leaves_a_fact_bearing_spoken_reply_alone():
    from friday.voice.brain_bridge import _recall_fact_guard

    meta = {"memory_recall": True, "fact": "my favorite color is teal."}
    assert _recall_fact_guard(meta, "answered", "Your favorite color is teal.") == (
        "Your favorite color is teal."
    )
    listed = f"Of course I remember, Boss:\n\n• {TEAL_CLEAN}"
    assert _recall_fact_guard(meta, "answered", listed) == listed


def test_guard_only_applies_to_answered_recalls_with_a_fact():
    from friday.voice.brain_bridge import _recall_fact_guard

    spoken = "some spoken form without the value"
    assert _recall_fact_guard(
        {"memory_recall": True, "fact": "my favorite color is teal."},
        "failed", spoken,
    ) == spoken
    assert _recall_fact_guard(
        {"fact": "my favorite color is teal."}, "answered", spoken,
    ) == spoken
    assert _recall_fact_guard(
        {"memory_recall": True}, "answered", spoken,
    ) == spoken


def test_send_applies_the_guard_to_the_http_result():
    import json as _json

    from friday.voice.brain_bridge import VoiceBrainBridge

    body = {
        "reply": (
            "Of course I remember, Boss. Here's what I'm holding onto:\n\n"
            f"• {CHAI}\n• {ZQ}"
        ),
        "metadata": {
            "memory_recall": True,
            "fact": "my favorite color is teal.",
            "remembered_count": 2,
        },
    }
    payload = _json.dumps(body).encode()

    class _Resp:
        status_code = 200

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def aiter_bytes(self):
            yield payload

    class _Client:
        def stream(self, *args, **kwargs):
            return _Resp()

    bridge = VoiceBrainBridge()
    result = asyncio.run(bridge._send(_Client(), "What is my favorite color?"))
    assert result["state"] == "answered"
    assert result["spoken_reply"] == "Your favorite color is teal."
    # The full reply is preserved for the record.
    assert "holding onto" in result["full_reply"]


# ---------------------------------------------------------------------------
# Worker side: the delivery watch delivers verbatim, never retells
# ---------------------------------------------------------------------------

def test_delivery_watch_uses_verbatim_instructions():
    src = (
        Path(__file__).resolve().parents[1]
        / "src" / "friday" / "voice" / "livekit_worker.py"
    ).read_text()
    # Both delivery sites (late result + unverbalized nudge) repeat the
    # settled spoken_reply under a repeat-verbatim instruction.
    assert src.count("Say the following text aloud exactly") == 2
    assert src.count('tool_choice="none"') >= 2
    # The improvisation prompts are gone.
    assert "Before anything else, tell Surendra the outcome" not in src
    assert "Give Surendra the result of his earlier request" not in src


def test_delivery_thresholds_unchanged():
    from friday.voice import livekit_worker as worker

    # Reviewed for FRD-014 and kept: healthy verbalizations land ≤~4 s
    # after a result, so a 12 s grace never races one; the re-run #4
    # loss was the nudge's ~20 s improvised generation, not the
    # threshold.
    assert worker._DELIVERY_GRACE_S == 12.0
    assert worker._DELIVERY_EXPIRE_S == 150.0
