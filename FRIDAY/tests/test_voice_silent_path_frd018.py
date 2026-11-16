"""TASK-FRD-018 (silent-path follow-up): the record that closed in
silence, and the fragment that was never dispatched.

Evidence (FRD-005 re-run #7, production, 2026-11-16 — see
~/workspace/frd-005-rerun7/STATE.md): bridge turn b3-e2a326 (recall
"What is my favorite color?") settled ANSWERED at 23:15:00.901 IST
while the participant was still connected. The session then spoke an
improvised memory dump instead of the settled reply, and the complete
journal contains ZERO 'VOICE delivery watch:' lines — no fire, no
verified delivery, no NON-VERBATIM error. FRD-018's guarantee (every
substitution leaves a greppable ERROR) did not hold for that record.

The pin (established from the journal + the deployed code): the
record was answered and not late-pending, so it could not take the
"close" outcome; the session was not closing, so the watch loop was
alive; had it still been pending at the first post-grace pass, the
fire branch would have journaled. The only pre-fire close left is
"own-verbalized": _result_verbalized's loose substance check judged
the dump as carrying the settled reply's substance — the settled
reply was itself composed from the recall gate's merged memory
bullets (chai + secret-number marker), and the dump paraphrases
those same bullets, sharing the incidental figure "9" and several
content words — and the watch step closed own-verbalized records
with NO journal line.

Fixture honesty: the settled reply's literal body is logged NOWHERE
(the brain journal records reply_chars=205 only), so SETTLED below
is RECONSTRUCTED from the evidenced bullet contents (the FRD-017
finding: the reply was composed from the chai bullet and the
ZQ-marker bullet). The dump, by contrast, is VERBATIM from the
worker journal (conversation_item_added, 23:15:10.705 IST).

The fix pinned here:
  * the substance check is tightened with a distinctive-figure gate
    (a settled reply's payload figures — >=4 digits — must actually
    be spoken; an incidental shared figure no longer suffices);
  * topic-only speech at/past the grace is a "substitute" outcome —
    journaled by the watch step as a NON-VERBATIM failure, never
    fired on;
  * every record close journals its reason, the watch flushes its
    pending records when the session closes, and list-cap evictions
    of unresolved records are journaled (source pins below);
  * dropped delegation fragments (a user STT final that lands while
    a bridge call is in flight and is never dispatched) leave a
    journal line — the delegation-split observability follow-up.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from friday.voice.livekit_worker import (  # noqa: E402
    _delivery_action,
    _distinctive_figures,
    _dispatch_followed,
    _figure_key,
    _fragment_flight_settled,
    _fragment_flight_started,
    _fragment_flush,
    _fragment_user_final,
    _new_fragment_watch,
    _result_verbalized,
    _result_verbalized_loose,
)

# RECONSTRUCTED from the evidenced bullets (see docstring) — the
# reply the brain composed for b3-e2a326: chai bullet + ZQ bullet.
SETTLED = (
    "Your favorite chai is masala chai, Boss, and you review the "
    "fleet every morning at 9. I also have your secret favorite "
    "number saved in your long-term memory — it is filed under the "
    "marker ZQ1794340686."
)

# VERBATIM from the re-run #7 worker journal: what the session
# actually spoke over the pending record.
DUMP = (
    "By the way, I remember that your favorite chai is masala chai "
    "and you review the fleet every morning at 9. I also have your "
    "secret favorite number saved."
)

FIGURES = ("Portfolio snapshot (Stratex, FUTURES mode): Balance: "
           "10,792.80, open positions: none, 9 closed trades, net +195.06")
FIGURES_PARAPHRASE = "Your balance is 10792.80, with nine closed trades so far."


def _record(spoken_reply, *, ts=1000.0, state="answered", **extra):
    record = {
        "turn_id": "b3-e2a326",
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
# The tightened substance check
# ---------------------------------------------------------------------------

def test_figure_key_canonicalizes_grouping_and_trailing_zeros():
    assert _figure_key("10,792.80") == _figure_key("10792.8")
    assert _figure_key("195.06") == "195.06"
    assert _figure_key("9") == "9"


def test_distinctive_figures_are_the_payload_figures():
    # A balance and a P&L figure are payload; a count of 9 is not.
    assert _distinctive_figures({"10792.8", "195.06", "9"}) == {
        "10792.8", "195.06"}


def test_the_loose_check_alone_waves_the_rerun7_dump_through():
    # This is the hole, documented: the dump shares the incidental
    # figure 9 and >=2 content words with the settled reply, so the
    # pre-fix check called it an own-verbalization.
    assert _result_verbalized_loose(SETTLED, [DUMP]) is True


def test_the_tightened_check_rejects_the_rerun7_dump():
    # The dump drops the reply's distinctive figure (the 10-digit
    # marker) — topic without payload is not a verbalization.
    assert _result_verbalized(SETTLED, [DUMP]) is False


def test_the_healthy_paraphrase_still_verbalizes():
    # The pinned FRD-012/018 behaviour: the snapshot paraphrase
    # carries the balance — the payload's head figure — so it stays
    # a valid own-verbalization under the tightened check.
    assert _result_verbalized(FIGURES, [FIGURES_PARAPHRASE]) is True
    assert _result_verbalized_loose(FIGURES, [FIGURES_PARAPHRASE]) is True


def test_incidental_figure_only_is_not_a_verbalization():
    assert _result_verbalized(FIGURES, [
        "That was from the 9 closed trades you asked about.",
    ]) is False


def test_figure_free_replies_still_verbalize_by_content_words():
    reply = ("Got it, Boss — locked in: your favourite colour is teal. "
             "That one's pinned — it never fades.")
    assert _result_verbalized(reply, [
        "By the way, about your earlier question, I've locked in that "
        "your favorite color is teal. It's pinned and saved in your "
        "memories.",
    ]) is True


def test_filler_is_still_not_a_verbalization():
    assert _result_verbalized(FIGURES, [
        "I am currently retrieving the latest Stratex data for you.",
    ]) is False
    assert _result_verbalized(FIGURES, [
        "It is currently 3:37 PM in Tokyo, Japan.",
    ]) is False


# ---------------------------------------------------------------------------
# _delivery_action: the re-run #7 sequence, decided out loud
# ---------------------------------------------------------------------------

def test_rerun7_sequence_dump_is_a_substitute_never_own_verbalized():
    record = _record(SETTLED)
    # Before the grace, the dump in the window decides nothing yet —
    # and crucially is NOT an own-verbalized close (the regression).
    assert _delivery_action(record, [DUMP], now=1005.0) == "wait"
    # At the grace: a substitution — journaled as a failed delivery
    # by the watch step, never fired on.
    assert _delivery_action(record, [DUMP], now=1013.0) == "substitute"
    # Even past the expiry horizon the accurate record is the
    # substitution, not a bare expiry.
    assert _delivery_action(record, [DUMP], now=1000.0 + 151.0) == "substitute"


def test_rerun7_record_without_the_dump_still_fires():
    record = _record(SETTLED)
    assert _delivery_action(record, [], now=1013.0) == "fire"


def test_the_settled_reply_spoken_in_full_is_own_verbalized():
    record = _record(SETTLED)
    assert _delivery_action(record, [SETTLED], now=1005.0) == "own-verbalized"
    record = _record(FIGURES)
    assert _delivery_action(
        record, [FIGURES_PARAPHRASE], now=1005.0) == "own-verbalized"


def test_unrelated_speech_keeps_the_fire_path():
    # A stall filler shares no substance with the result: the proven
    # late-delivery pattern (fire at the grace) is unchanged.
    record = _record(FIGURES)
    assert _delivery_action(record, [
        "I am currently retrieving the latest Stratex data for you.",
    ], now=1013.0) == "fire"


# ---------------------------------------------------------------------------
# Dropped-fragment tracker (delegation-split observability)
# ---------------------------------------------------------------------------

def test_fragment_dropped_when_no_bridge_call_follows_it():
    state = _new_fragment_watch()
    _fragment_flight_started(
        state, "b1", "Ask Stratex for my portfolio balance", 100.0)
    # Fragment 2 lands while b1 is in flight: a suspect.
    assert _fragment_user_final(
        state, "Also include the ledger of my closed trades",
        101.0) == []
    _fragment_flight_settled(state, "b1")
    # One final of grace: the next final does not convict it yet.
    assert _fragment_user_final(
        state, "And what about my open orders?", 103.0) == []
    # The final after that proves it: no bridge call ever followed.
    dropped = _fragment_user_final(
        state, "What time is it in Tokyo?", 104.0)
    assert [s["text"] for s in dropped] == [
        "Also include the ledger of my closed trades"]


def test_fragment_followed_by_a_bridge_call_clears_silently():
    state = _new_fragment_watch()
    _fragment_flight_started(state, "b1", "Check the fleet status", 100.0)
    _fragment_user_final(state, "Remember my favorite color is teal", 101.0)
    _fragment_flight_settled(state, "b1")
    # The model DID act on the fragment: a later dispatch carries it.
    _fragment_flight_started(
        state, "b2", "Remember this: my favorite color is teal", 102.0)
    _fragment_flight_settled(state, "b2")
    assert _fragment_user_final(state, "What is my favorite color?",
                                103.0) == []
    assert _fragment_user_final(state, "Thanks, that is all", 104.0) == []
    assert state["suspects"] == []
    assert _fragment_flush(state) == []


def test_fragment_flush_reports_only_the_unfollowed():
    state = _new_fragment_watch()
    _fragment_flight_started(state, "b2", "Remember my favorite color",
                             105.0)
    _fragment_user_final(state, "What is my favorite color?", 106.0)
    _fragment_flight_settled(state, "b2")
    _fragment_flight_started(
        state, "b3", "What is my favorite color? Recall it", 108.0)
    # The goodbye lands while b3 is still in flight: a suspect too.
    _fragment_user_final(state, "That is all, goodbye", 109.0)
    dropped = _fragment_flush(state)
    # The recall suspect was followed by b3 (cleared); the goodbye
    # was followed by nothing (reported).
    assert [s["text"] for s in dropped] == ["That is all, goodbye"]
    # The flush is idempotent.
    assert _fragment_flush(state) == []


def test_final_with_no_flight_is_never_a_suspect():
    state = _new_fragment_watch()
    assert _fragment_user_final(state, "Hello Friday", 100.0) == []
    assert state["suspects"] == []
    assert _dispatch_followed(state, {"ts": 1.0, "text": "anything"}) is False


# ---------------------------------------------------------------------------
# The bridge dispatch observer: start/settle pair 1:1 by turn_id
# ---------------------------------------------------------------------------

def _bridge_with_observers():
    from friday.voice.brain_bridge import VoiceBrainBridge

    events = {"dispatch": [], "result": []}
    bridge = VoiceBrainBridge(
        result_observer=events["result"].append,
        dispatch_observer=events["dispatch"].append)
    return bridge, events


def test_refusal_settles_without_a_dispatch_notification():
    bridge, events = _bridge_with_observers()
    result = asyncio.run(bridge.execute(""))
    assert result["state"] == "refused"
    assert events["dispatch"] == []
    assert [r["state"] for r in events["result"]] == ["refused"]


def test_substantive_call_pairs_dispatch_start_with_its_settle():
    bridge, events = _bridge_with_observers()

    async def fake_dispatch(text, turn_id):
        return {"state": "answered", "spoken_reply": "Done, Boss."}

    bridge._dispatch = fake_dispatch
    result = asyncio.run(bridge.execute("Check my Stratex balance"))
    assert result["state"] == "answered"
    assert len(events["dispatch"]) == 1
    assert len(events["result"]) == 1
    assert events["dispatch"][0]["turn_id"] == events["result"][0]["turn_id"]
    assert events["dispatch"][0]["request"] == "Check my Stratex balance"


def test_a_failing_dispatch_observer_never_breaks_a_call():
    from friday.voice.brain_bridge import VoiceBrainBridge

    def boom(_info):
        raise RuntimeError("observer down")

    bridge = VoiceBrainBridge(dispatch_observer=boom)

    async def fake_dispatch(text, turn_id):
        return {"state": "answered", "spoken_reply": "Done, Boss."}

    bridge._dispatch = fake_dispatch
    result = asyncio.run(bridge.execute("Check my Stratex balance"))
    assert result["state"] == "answered"


# ---------------------------------------------------------------------------
# Source pins: no silent close remains in the watch step
# ---------------------------------------------------------------------------

def _worker_source() -> str:
    path = (Path(__file__).resolve().parents[1]
            / "src" / "friday" / "voice" / "livekit_worker.py")
    return path.read_text(encoding="utf-8")


def test_every_close_journals_its_reason():
    src = _worker_source()
    # The close branch's reason line (split across two literals).
    assert "closed " in src and "without delivery" in src
    # The substitute outcome's NON-VERBATIM failure line.
    assert "NON-VERBATIM substitute" in src
    assert "the settled reply was NOT delivered" in src
    # The own-verbalized close is journaled too.
    assert "verbalized by the model itself" in src


def test_the_watch_flushes_on_stop_from_both_exits():
    src = _worker_source()
    assert "still pending when the watch stopped" in src
    assert "dropped from the watch list" in src
    assert "delivery is due but could not fire" in src
    # Defined once, called from the session-close path and from the
    # watch loop's exit (the flush itself is idempotent).
    watch_turns = src.split("async def _watch_turns", 1)[1].split(
        "async def _deliver_memory_when_ready", 1)[0]
    assert "_flush_watch_on_stop()" in watch_turns
    close_fn = src.split("async def _close_session_when_empty", 1)[1]
    assert "_flush_watch_on_stop()" in close_fn


def test_dropped_fragment_journal_line_exists():
    src = _worker_source()
    assert "VOICE dropped-fragment suspect" in src
    assert "it was never dispatched" in src
