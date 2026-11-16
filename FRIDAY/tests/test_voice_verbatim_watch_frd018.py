"""TASK-FRD-018: the delivery watch improvised on a model-composed reply.

Evidence (FRD-005 re-run #6, production, 2026-11-16 — see
~/workspace/frd-005-rerun6/STATE.md): the recall turn settled at
20:09:23 with a 205-char MODEL-COMPOSED spoken_reply (the FRD-014
deterministic answer was bypassed — TASK-FRD-017's defect). The model
verbalized nothing in-turn. The FRD-012/014 delivery watch fired at
20:09:48 ("unverbalized 25s after delivery; nudging the session to
speak it") with its repeat-verbatim generate_reply instruction — and
the session spoke an invented memory dump instead ("Of course I
remember, Boss. Here's what I'm holding onto: my favorite chai is
masala chai and I review the fleet every morning at 9. My secret
favorite number is owner favorite test marker ZQ1794340686."). The
old code marked the record nudged at call time and never compared
what was actually said with the settled text: the substitution was
discovered by the acceptance participant, not the system. Contrast
re-run #5's drill, where the same instruction repeated a short
templated reply word for word.

Root cause (pinned by the plugin source, livekit-plugins-google
1.8.11): the production model gemini-3.8-live takes no reply
placeholder, so generate_reply wraps instructions in
<instructions>…</instructions> and sends them as a USER-ROLE turn;
tool_choice="none" has no per-response existence on the Gemini Live
API (the plugin emulates it by rejecting tool calls, and re-run #6's
journal carries the warning). The "verbatim instruction" is a
conversational suggestion to a generative model — compliance is
content- and context-dependent. session.say() is unavailable
(supports_say=False) and the worker has no other speech synthesizer,
so the fix is the watch's own discipline: fire only with an exact
settled text in hand (never on an empty one — the late-result
registry files spoken_reply="" entries, which the old late site
delivered unguarded), and verify every fired delivery strictly
against the settled text, never re-firing a failed one.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from friday.voice.livekit_worker import (  # noqa: E402
    _delivery_action,
    _result_verbalized,
    _spoken_matches_settled,
    _verbatim_deliverable,
    _verbatim_delivery_instruction,
)

# A representative model-composed settled reply in the shape of the
# re-run #6 case (answer-shaped prose composed by the brain's
# cognitive layer, ~200 chars — NOT the deterministic template).
COMPOSED_REPLY = (
    "Of course, Boss. Your favorite color is teal — you told me that "
    "earlier today and I have kept it in your long-term memory ever "
    "since, right alongside your other preferences for the fleet."
)

# What the session actually spoke in re-run #6 after the watch fired
# (verbatim from the run's participant record).
IMPROVISED_DUMP = (
    "Of course I remember, Boss. Here's what I'm holding onto: my "
    "favorite chai is masala chai and I review the fleet every "
    "morning at 9. My secret favorite number is owner favorite test "
    "marker ZQ1794340686."
)

FIGURES = ("Portfolio snapshot (Stratex, FUTURES mode): Balance: "
           "10,792.80, open positions: none, 9 closed trades, net +195.06")
FIGURES_PARAPHRASE = "Your balance is 10792.80, with nine closed trades so far."


def _record(spoken_reply, *, ts=1000.0, state="answered", **extra):
    record = {
        "turn_id": "b4-e2a326",
        "state": state,
        "spoken_reply": spoken_reply,
        "late_pending": False,
        "ts": ts,
        "nudged": False,
        "done": False,
    }
    record.update(extra)
    return record


# ---------------------------------------------------------------------------
# The payload gate: no settled text, no fire — silence over improvisation
# ---------------------------------------------------------------------------

def test_deliverable_gate_rejects_unavailable_text():
    assert _verbatim_deliverable(None) is None
    assert _verbatim_deliverable("") is None
    assert _verbatim_deliverable("   \n ") is None
    assert _verbatim_deliverable(123) is None
    assert _verbatim_deliverable(["Done."]) is None


def test_deliverable_gate_passes_the_exact_settled_text():
    assert _verbatim_deliverable("Done.") == "Done."
    assert _verbatim_deliverable(COMPOSED_REPLY) == COMPOSED_REPLY
    assert _verbatim_deliverable("  Done.  ") == "Done."


def test_empty_settled_reply_is_silence_never_fire():
    # The late-result registry files spoken_reply="" when a brain
    # result carries none; at the grace the only lawful action is
    # staying silent — a repeat instruction with no text after the
    # colon can only be satisfied by inventing content.
    record = _record("")
    assert _delivery_action(record, [], now=1013.0) == "silent-unavailable"
    record_none = _record(None)
    assert _delivery_action(record_none, [], now=1013.0) == "silent-unavailable"


# ---------------------------------------------------------------------------
# The one instruction builder (both delivery sites share it)
# ---------------------------------------------------------------------------

def test_instruction_builder_wording_is_the_frd014_instruction():
    assert _verbatim_delivery_instruction("Done.") == (
        "Say the following text aloud exactly, word for word, adding "
        "nothing and leaving nothing out: Done."
    )


def test_instruction_wording_lives_in_exactly_one_place():
    src = (Path(__file__).resolve().parents[1] / "src" / "friday"
           / "voice" / "livekit_worker.py").read_text()
    # The helper is the only site that may contain the wording; a
    # second inline copy is how the two delivery sites drift apart.
    assert src.count("Say the following text aloud exactly") == 1


# ---------------------------------------------------------------------------
# The strict verbatim check
# ---------------------------------------------------------------------------

def test_strict_match_accepts_a_true_repeat():
    assert _spoken_matches_settled(COMPOSED_REPLY, [COMPOSED_REPLY]) is True
    # Transcription variance is case/punctuation only, never wording.
    assert _spoken_matches_settled(
        "Your favorite color is teal.",
        ["your favorite color is teal"],
    ) is True
    # A repeat split across two assistant items still matches.
    cut = COMPOSED_REPLY.index("ever since")
    assert _spoken_matches_settled(
        COMPOSED_REPLY,
        [COMPOSED_REPLY[:cut], COMPOSED_REPLY[cut:]],
    ) is True


def test_strict_match_rejects_the_rerun6_improvisation():
    # The production regression, reproduced: the settled reply was in
    # hand, the watch fired, and THIS is what the session said.
    assert _spoken_matches_settled(COMPOSED_REPLY, [IMPROVISED_DUMP]) is False


def test_strict_match_rejects_paraphrase_that_the_loose_check_accepts():
    # The loose substance check is right for "the model verbalized it
    # itself" — and wrong for a watch delivery, which is verbatim or
    # it is not a delivery. Pin the distinction.
    assert _result_verbalized(FIGURES, [FIGURES_PARAPHRASE]) is True
    assert _spoken_matches_settled(FIGURES, [FIGURES_PARAPHRASE]) is False


def test_strict_match_rejects_reordering_and_emptiness():
    assert _spoken_matches_settled(
        "Your favorite color is teal.",
        ["Teal is your favorite color."],
    ) is False
    assert _spoken_matches_settled(COMPOSED_REPLY, []) is False
    assert _spoken_matches_settled("", [COMPOSED_REPLY]) is False


# ---------------------------------------------------------------------------
# The watch decision: the re-run #6 sequence, step by step
# ---------------------------------------------------------------------------

def test_rerun6_sequence_fire_then_mismatch_never_verified():
    record = _record(COMPOSED_REPLY)
    # Within the grace: nothing to decide.
    assert _delivery_action(record, [], now=1005.0) == "wait"
    # At the grace, unverbalized, settled text in hand: fire once.
    assert _delivery_action(record, [], now=1013.0) == "fire"
    # The watch fired; the session then spoke the improvised dump.
    # The old code had already recorded this as a successful nudge —
    # the decision now is a mismatch: NOT delivered, never "verified".
    record["nudged"] = True
    record["fired_ts"] = 1013.0
    assert _delivery_action(
        record, [IMPROVISED_DUMP], now=1040.0) == "mismatch"


def test_fired_delivery_verified_only_by_the_settled_words():
    record = _record(COMPOSED_REPLY, nudged=True, fired_ts=1013.0)
    assert _delivery_action(record, [COMPOSED_REPLY], now=1030.0) == "verified"
    # Silence after firing is a wait, then an expiry — never a pass.
    assert _delivery_action(record, [], now=1030.0) == "wait"
    assert _delivery_action(record, [], now=1013.0 + 151.0) == "expire"


def test_prefire_behaviour_is_unchanged():
    # The model verbalizing the result itself still closes the record
    # (substance check), exactly as FRD-012 designed.
    record = _record(FIGURES)
    assert _delivery_action(
        record, [FIGURES_PARAPHRASE], now=1005.0) == "own-verbalized"
    # Unwatchable outcomes are the model's conversation, not outcomes.
    assert _delivery_action(
        _record("x", state="confirmation_required"), [], now=1013.0) == "close"
    assert _delivery_action(
        _record("x", late_pending=True), [], now=1013.0) == "close"
    # A stranded result still expires with its journal line.
    assert _delivery_action(_record(FIGURES), [], now=1000.0 + 151.0) == "expire"
