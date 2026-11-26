"""TASK-FRD-019: a dropped STT fragment is recovered, not just journalled.

Evidence (FRD-005 re-run #8, run 20261117-055507, production worker
journal, S1):

- 05:55:31.434 user final 1: "Friday, check Stratex for me."
- 05:55:31.609 bridge send b1-4e3cfa with ONLY fragment 1's request
  ("Check Stratex for me." — the model called on the first final).
- 05:55:37.200 an interim carrying fragment 2's full text; the final
  itself landed 05:55:41.800: "What is the balance? How many open
  positions are there? And how many closed trades are in the ledger?"
- Fragment 2 was NEVER dispatched. It surfaced only via the FRD-015
  tracker's dropped-fragment suspect ERROR. The follow-up question
  that landed during the same flight (interim 05:55:48.604) never
  became a bridge call either — the model absorbed it into the
  pending delivery and its answer arrived merged, ~22 s late.
- b1 settled 05:55:51.8 (brain turn 20.20 s).

Why recovery, not a pre-dispatch settle: the journal shows NO
transcription signal of any kind between +0.2 s and +5.8 s — interims
arrive once per segment, at segment end — so at dispatch time there
is no evidence a continuation exists; a settle long enough to catch
this split (>= 11 s) would tax EVERY command and break the owner's
speed-first bar. The remember leg in the same call "consolidated"
only because the model never called on its fragment A (nothing
actionable); model-side turn assembly is the only consolidation
that exists, and it is discretionary. The fix pinned here makes the
WORKER guarantee the whole turn reaches the brain: once the flight
a suspect landed during has settled, a suspect still carrying
substance no dispatch covered is handed out exactly once
(_fragment_recovery_due) and the delivery-watch pass dispatches its
text as its own bridge call; the result flows through the ordinary
result observer into the FRD-012/018 delivery watch.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

pytestmark = [pytest.mark.unit]

from friday.voice.livekit_worker import (  # noqa: E402
    _fragment_flight_settled,
    _fragment_flight_started,
    _fragment_flush,
    _fragment_recovery_due,
    _fragment_user_final,
    _new_fragment_watch,
)

# The run #8 shapes, verbatim from the journal.
FRAG1_REQUEST = "Check Stratex for me."
FRAG2 = (
    "What is the balance? How many open positions are there? "
    "And how many closed trades are in the ledger?"
)
FOLLOWUP = "How many closed trades are in the ledger exactly?"

# The FRD-019(b) drill shapes (Phase B): a substantive fragment
# followed by two contentless fillers before its flight settles.
DRILL_G1_REQUEST = "Please remind me of my favorite color."
DRILL_G2 = "And my favorite destination city?"


def _run8_state():
    """The delegation flight with fragment 2 landed mid-flight."""
    state = _new_fragment_watch()
    _fragment_flight_started(state, "b1", FRAG1_REQUEST, 100.0)
    _fragment_user_final(state, FRAG2, 110.0)
    return state


def test_split_delegation_fragment_becomes_due_after_its_flight_settles():
    state = _run8_state()
    # Still in flight: not due — the model may yet call on it, and
    # the flight's own result has not landed.
    assert _fragment_recovery_due(state, 115.0) == []
    _fragment_flight_settled(state, "b1")
    due = _fragment_recovery_due(state, 121.0)
    assert len(due) == 1
    assert due[0]["text"] == FRAG2
    assert due[0]["during"] == ["b1"]


def test_recovery_is_handed_out_exactly_once():
    state = _run8_state()
    _fragment_flight_settled(state, "b1")
    assert len(_fragment_recovery_due(state, 121.0)) == 1
    assert _fragment_recovery_due(state, 122.0) == []
    assert _fragment_recovery_due(state, 130.0) == []


def test_fragment_the_model_picked_up_later_is_not_recovered():
    state = _run8_state()
    # The model composes a follow-up call carrying fragment 2's
    # substance before the first flight settles — nothing was lost.
    _fragment_flight_started(state, "b2", FRAG2, 115.0)
    _fragment_flight_settled(state, "b2")
    _fragment_flight_settled(state, "b1")
    assert _fragment_recovery_due(state, 121.0) == []


def test_fragment_carried_by_its_own_flight_is_not_recovered():
    state = _new_fragment_watch()
    whole = f"{FRAG1_REQUEST} {FRAG2}"
    _fragment_flight_started(state, "b1", whole, 100.0)
    _fragment_user_final(state, FRAG2, 110.0)
    _fragment_flight_settled(state, "b1")
    assert _fragment_recovery_due(state, 121.0) == []


def test_followup_that_landed_during_the_flight_is_also_due():
    # Re-run #8's starved follow-up: a separate question that landed
    # during the delegation flight and never got a bridge call. It is
    # a suspect like any other and earns its own recovery dispatch.
    state = _run8_state()
    _fragment_user_final(state, FOLLOWUP, 118.0)
    _fragment_flight_settled(state, "b1")
    due = _fragment_recovery_due(state, 121.0)
    assert [s["text"] for s in due] == [FRAG2, FOLLOWUP]


def test_stale_fragment_is_not_recovered():
    state = _run8_state()
    _fragment_flight_settled(state, "b1")
    # 121 s after the fragment landed the conversation has moved on.
    assert _fragment_recovery_due(state, 231.0) == []


def test_contentless_final_is_not_recovered():
    state = _new_fragment_watch()
    _fragment_flight_started(state, "b1", FRAG1_REQUEST, 100.0)
    _fragment_user_final(state, "Okay.", 110.0)
    _fragment_flight_settled(state, "b1")
    assert _fragment_recovery_due(state, 121.0) == []


def test_final_with_nothing_in_flight_is_never_a_suspect():
    state = _new_fragment_watch()
    _fragment_user_final(state, FRAG2, 110.0)
    assert state["suspects"] == []
    assert _fragment_recovery_due(state, 121.0) == []


def test_recovered_fragment_leaves_the_session_flush_clean():
    # Once the recovery dispatch itself has run (a new flight whose
    # request IS the fragment), the session-end flush must not report
    # the fragment as dropped — it reached the brain.
    state = _run8_state()
    _fragment_flight_settled(state, "b1")
    due = _fragment_recovery_due(state, 121.0)
    assert len(due) == 1
    _fragment_flight_started(state, "b9", due[0]["text"], 125.0)
    _fragment_flight_settled(state, "b9")
    assert _fragment_flush(state) == []


def test_unrelated_second_flight_does_not_block_recovery():
    # A suspect is tied to the flight it landed during; a later,
    # unrelated call still being in flight does not hold it back
    # (the bridge's own send lock serializes the actual sends).
    state = _run8_state()
    _fragment_flight_settled(state, "b1")
    _fragment_flight_started(state, "b7", "What time is it?", 119.0)
    due = _fragment_recovery_due(state, 121.0)
    assert [s["text"] for s in due] == [FRAG2]


# ---------------------------------------------------------------------------
# FRD-019(b): a fragment proven dropped BEFORE its flight settles
# (two further finals land first) must still be recovered. Pre-fix,
# _fragment_user_final consumed proven suspects — removed them from
# state["suspects"] — while _fragment_recovery_due only ever saw
# listed suspects, so the two fates were mutually exclusive and this
# exact sequence was journalled but never recovered (drill Phase B).
# ---------------------------------------------------------------------------

def _phase_b_state():
    """The drill's Phase B sequence: G2 lands during G1's flight;
    two further finals land before the flight settles, the second
    of which proves G2 dropped."""
    state = _new_fragment_watch()
    _fragment_flight_started(state, "b1", DRILL_G1_REQUEST, 100.0)
    _fragment_user_final(state, DRILL_G2, 110.0)
    _fragment_user_final(state, "Okay.", 112.0)
    _fragment_user_final(state, "Yes, please.", 114.0)
    return state


def test_fragment_proven_by_two_further_finals_is_still_recovered():
    state = _new_fragment_watch()
    _fragment_flight_started(state, "b1", DRILL_G1_REQUEST, 100.0)
    assert _fragment_user_final(state, DRILL_G2, 110.0) == []
    assert _fragment_user_final(state, "Okay.", 112.0) == []
    # The second further final proves G2 dropped: it is returned for
    # journalling exactly as before the fix...
    proven = _fragment_user_final(state, "Yes, please.", 114.0)
    assert [s["text"] for s in proven] == [DRILL_G2]
    # ...but it STAYS listed, so the recovery pass can still see it.
    assert any(s["text"] == DRILL_G2 for s in state["suspects"])
    # A fourth final does not report it a second time.
    again = _fragment_user_final(state, "Okay.", 116.0)
    assert DRILL_G2 not in [s["text"] for s in again]
    # Once the flight settles, the proven fragment is due — once.
    _fragment_flight_settled(state, "b1")
    due = _fragment_recovery_due(state, 121.0)
    assert [s["text"] for s in due] == [DRILL_G2]
    assert _fragment_recovery_due(state, 122.0) == []


def test_proven_fragment_covered_by_a_later_dispatch_is_not_recovered():
    # Proof does not force recovery: if the model picks the proven
    # fragment up in a later call before its flight settles, the
    # covering dispatch resolves it — it must never become due.
    state = _phase_b_state()
    _fragment_flight_started(state, "b2", DRILL_G2, 116.0)
    _fragment_flight_settled(state, "b2")
    _fragment_flight_settled(state, "b1")
    assert _fragment_recovery_due(state, 121.0) == []


def test_flush_does_not_re_report_a_proven_fragment():
    # The proven fragment already left its journal line at proof
    # time; the session-end flush must not report it a second time.
    # The unproven fillers — never proven, never followed — still
    # flush exactly as before.
    state = _phase_b_state()
    flushed = _fragment_flush(state)
    assert [s["text"] for s in flushed] == ["Okay.", "Yes, please."]
    assert state["suspects"] == []


# ---------------------------------------------------------------------------
# Wiring: _voice_tools hands the worker the bridge it built
# ---------------------------------------------------------------------------

def test_voice_tools_registers_the_bridge_in_the_sink(monkeypatch):
    import friday.voice.brain_bridge as bb
    from friday.voice.livekit_worker import _voice_tools

    built = {}

    class _FakeBridge:
        def __init__(self, **kwargs):
            built["bridge_kwargs"] = kwargs

    def _fake_build(**kwargs):
        built["build_kwargs"] = kwargs
        return ["tool"]

    monkeypatch.setattr(bb, "VoiceBrainBridge", _FakeBridge)
    monkeypatch.setattr(bb, "build_voice_tools", _fake_build)

    sink = {}
    tools = _voice_tools(
        result_observer="ro", dispatch_observer="do",
        turn_transcript_provider="tp", bridge_sink=sink)
    assert tools == ["tool"]
    assert isinstance(sink["bridge"], _FakeBridge)
    # The explicitly built bridge carries the SAME observers the tool
    # path would have used — the recovery call settles into the same
    # delivery watch.
    assert built["bridge_kwargs"] == {
        "result_observer": "ro",
        "dispatch_observer": "do",
        "turn_transcript_provider": "tp",
    }
    assert built["build_kwargs"] == {"bridge": sink["bridge"]}

    # No sink: the historical construction path is untouched.
    built.clear()
    tools = _voice_tools(
        result_observer="ro", dispatch_observer="do",
        turn_transcript_provider="tp")
    assert tools == ["tool"]
    assert built["build_kwargs"] == {
        "result_observer": "ro",
        "turn_transcript_provider": "tp",
        "dispatch_observer": "do",
    }


def test_worker_wiring_source_pins():
    src = (
        Path(__file__).resolve().parents[1]
        / "src" / "friday" / "voice" / "livekit_worker.py"
    ).read_text()
    # The delivery-watch pass consumes the due list and dispatches
    # through the job-level recovery coroutine; sessions register
    # their bridge in the job-level slot.
    assert src.count("_fragment_recovery_due(") >= 2  # def + watch pass
    assert src.count("_recover_dropped_fragment(") >= 2  # def + watch pass
    assert "bridge_sink=bridge_slot" in src
    assert "_FRAGMENT_RECOVERY_MAX_AGE_S = 120.0" in src


# ---------------------------------------------------------------------------
# TASK-FRD-022 (PR #865 review follow-up): a recovered fragment that
# hits the confirmation gate is NEVER executed. The reviewer verified
# this structurally — the recovery dispatch awaits the same
# VoiceBrainBridge.execute() as the tool path, whose confirmation
# gate runs before the only submission seam (bridge._send) — but the
# case was not pinned by a test. Pin it here so it cannot regress:
# the gated fragment still becomes due (the tracker hands out
# undispatched substance; gating is the bridge's job, not the
# tracker's), and its recovery dispatch settles confirmation_required
# with the submission seam never reached.
# ---------------------------------------------------------------------------

GATED_FRAG2 = "And close all my Stratex positions."


class _SendRecorder:
    """Fake bridge._send (the submission seam): records every call."""

    def __init__(self):
        self.calls = []

    async def __call__(self, client, text):
        self.calls.append(text)
        return {"state": "answered", "spoken_reply": "Done."}


def _run(coro):
    import asyncio

    return asyncio.new_event_loop().run_until_complete(coro)


def test_recovered_fragment_that_hits_the_confirmation_gate_is_never_executed(
        monkeypatch):
    from friday.voice import confirmation_policy as policy
    from friday.voice.brain_bridge import VoiceBrainBridge

    # The gated fragment lands during the read-only Stratex flight.
    # Against that flight's request it shares only 'stratex' (one
    # content word, no figures), so it is genuinely undispatched
    # substance and becomes due once the flight settles — once.
    state = _new_fragment_watch()
    _fragment_flight_started(state, "b1", FRAG1_REQUEST, 100.0)
    _fragment_user_final(state, GATED_FRAG2, 110.0)
    _fragment_flight_settled(state, "b1")
    due = _fragment_recovery_due(state, 121.0)
    assert [s["text"] for s in due] == [GATED_FRAG2]
    assert _fragment_recovery_due(state, 122.0) == []

    # The recovery dispatch itself — what _recover_dropped_fragment
    # awaits on the session bridge — with the REAL confirmation gate,
    # constructed explicitly so the pin does not depend on env. The
    # fragment's shape (close + positions, same clause) classifies
    # trade/sensitive, so the gate must stop it.
    seen = []
    recorder = _SendRecorder()
    bridge = VoiceBrainBridge(
        confirmation_gate=policy.ConfirmationGate(),
        result_observer=seen.append,
    )
    monkeypatch.setattr(bridge, "_send", recorder)
    result = _run(bridge.execute(due[0]["text"]))

    # The gate settles the recovery call: the owner is asked, the
    # result observer closes the record with the gated state (the
    # delivery watch's ordinary close for a gated call) — and the
    # submission seam was NEVER reached. Nothing was executed.
    assert result["state"] == "confirmation_required"
    assert result["confirmation_required"] is True
    assert recorder.calls == []
    assert len(seen) == 1
    assert seen[0]["state"] == "confirmation_required"


# ---------------------------------------------------------------------------
# TASK-VOI-043 (P0, owner live test 2026-11-25): zero dropped fragments
# + no arbitrary speech cancellation.
#
# (c) leg 1 — script-blindness: _distinctive_tokens is ASCII-Latin
# only, so a final transcribed in Devanagari/Telugu script carried
# ZERO tokens and the recovery pass read it as "no distinctive
# substance" — never recovered. The owner session's dropped fragment
# was exactly such a final (Hindi 10:24:52 UTC, Telugu 10:25:00
# UTC). _fragment_tokens keeps the Latin rule byte-identical and
# adds non-Latin letter runs; the shapes below are verbatim from
# that journal.
#
# (c) leg 2 — stuck flight: a bridge call cancelled mid-flight (the
# SDK cancels a tool call on interruption; the arbitrary-cancellation
# backstop cancels the whole speech) never settled, because
# execute() let CancelledError propagate without _settle — the result
# observer never fired, so the flight stayed in-flight FOREVER and
# any suspect that landed during it could never become due.
# ---------------------------------------------------------------------------

# Owner session 2026-11-25 10:24:52 / 10:25:00 UTC, verbatim.
HINDI_FRAG = "ए, पड़को।"
TELUGU_FRAG = "Stratex స్పష్టంగా తెలుసు."


def test_hindi_script_fragment_is_recovered():
    # Pre-fix this returned []: _distinctive_tokens("ए, पड़को।")
    # is (set(), set()), so the recovery pass skipped it as
    # contentless. The Devanagari content word "पड़को" is substance.
    state = _new_fragment_watch()
    _fragment_flight_started(state, "b1", FRAG1_REQUEST, 100.0)
    _fragment_user_final(state, HINDI_FRAG, 110.0)
    _fragment_flight_settled(state, "b1")
    due = _fragment_recovery_due(state, 121.0)
    assert [s["text"] for s in due] == [HINDI_FRAG]
    assert _fragment_recovery_due(state, 122.0) == []


def test_telugu_script_fragment_is_recovered():
    state = _new_fragment_watch()
    _fragment_flight_started(state, "b1", FRAG1_REQUEST, 100.0)
    _fragment_user_final(state, TELUGU_FRAG, 110.0)
    _fragment_flight_settled(state, "b1")
    due = _fragment_recovery_due(state, 121.0)
    assert [s["text"] for s in due] == [TELUGU_FRAG]


def test_fragment_tokens_are_script_aware():
    from friday.voice.livekit_worker import (
        _distinctive_tokens,
        _fragment_tokens,
    )

    # The old helper is untouched — and still blind by design; the
    # fragment path no longer uses it.
    assert _distinctive_tokens(HINDI_FRAG) == (set(), set())
    # The fragment helper sees the Devanagari content word.
    numbers, words = _fragment_tokens(HINDI_FRAG)
    assert numbers == set()
    assert "पड़को" in words
    assert "ए" not in words  # a 1-code-point particle: no substance
    # Telugu: the Latin fleet name plus the Telugu content words.
    numbers, words = _fragment_tokens(TELUGU_FRAG)
    assert numbers == set()
    assert "stratex" in words
    assert "స్పష్టంగా" in words
    assert "తెలుసు" in words
    # Latin behaviour is byte-identical to the old helper.
    assert _fragment_tokens(FRAG2) == _distinctive_tokens(FRAG2)
    assert _fragment_tokens("Okay.") == _distinctive_tokens("Okay.")
    assert _fragment_tokens("Okay.") == (set(), set())
    # Figures still match across scripts.
    numbers, words = _fragment_tokens("Balance 10,444.12 please")
    assert "10444.12" in numbers


def test_fragment_word_runs_keep_combining_marks_attached():
    from friday.voice.livekit_worker import _fragment_word_runs

    # A \w split shreds "पड़को" (nukta + vowel sign are not word
    # characters) into 1-code-point pieces; letter+mark runs keep
    # the word whole — this is what makes the test above pass.
    assert _fragment_word_runs(HINDI_FRAG) == ["ए", "पड़को"]
    assert _fragment_word_runs(TELUGU_FRAG) == [
        "Stratex", "స్పష్టంగా", "తెలుసు"]
    assert _fragment_word_runs("don't follow-up, please.") == [
        "don", "t", "follow", "up", "please"]


def test_non_latin_fragment_covered_by_a_later_dispatch_is_not_recovered():
    # Coverage matching works across scripts too: a later dispatch
    # carrying the fragment's own substance resolves it — recovery
    # must not fire for a fragment the model did pick up.
    state = _new_fragment_watch()
    _fragment_flight_started(state, "b1", FRAG1_REQUEST, 100.0)
    _fragment_user_final(state, TELUGU_FRAG, 110.0)
    _fragment_flight_started(state, "b2", TELUGU_FRAG, 115.0)
    _fragment_flight_settled(state, "b2")
    _fragment_flight_settled(state, "b1")
    assert _fragment_recovery_due(state, 121.0) == []


def test_non_latin_fragment_sharing_one_word_only_is_still_recovered():
    # One shared word is not coverage (the rule needs a figure or
    # >= 2 shared words): a later dispatch that only repeats the
    # fleet name does not resolve the Telugu fragment.
    state = _new_fragment_watch()
    _fragment_flight_started(state, "b1", FRAG1_REQUEST, 100.0)
    _fragment_user_final(state, TELUGU_FRAG, 110.0)
    _fragment_flight_started(
        state, "b2", "Stratex balance is 10,444.12.", 115.0)
    _fragment_flight_settled(state, "b2")
    _fragment_flight_settled(state, "b1")
    due = _fragment_recovery_due(state, 121.0)
    assert [s["text"] for s in due] == [TELUGU_FRAG]


# --- (c) leg 2: a cancelled bridge call settles its flight ----------

class _BlockingSend:
    """Fake bridge._send that blocks until the test releases it.

    fail_first=True: the first (blocked) send raises once released,
    so no late result is filed and nothing is cached — the property
    the not-cached test needs. Otherwise the released send answers.
    """

    def __init__(self, fail_first=False):
        self.calls = []
        self.released = asyncio.Event()
        self.fail_first = fail_first

    async def __call__(self, client, text):
        self.calls.append(text)
        if len(self.calls) == 1:
            await self.released.wait()
            if self.fail_first:
                raise RuntimeError("send failed")
        return {"state": "answered", "spoken_reply": "Done."}


def _cancelled_execute_case():
    """Drive one execute() to cancellation; return the observers."""
    import friday.voice.brain_bridge as bb
    from friday.voice.brain_bridge import VoiceBrainBridge

    async def _case():
        dispatches, results = [], []
        send = _BlockingSend()
        bridge = VoiceBrainBridge(
            dispatch_observer=dispatches.append,
            result_observer=results.append,
        )
        bridge._send = send
        task = asyncio.ensure_future(
            bridge.execute("What is the Stratex balance?"))
        await asyncio.sleep(0.2)
        assert len(dispatches) == 1  # the flight started
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        else:
            raise AssertionError("cancelled execute() must raise")
        # Let the shielded send finish so its late result files
        # cleanly instead of dangling past the test loop.
        send.released.set()
        await asyncio.sleep(0.2)
        late = bb.pop_late_results()
        return dispatches, results, send, late

    return _run(_case())


def test_cancelled_execute_settles_the_flight_exactly_once():
    dispatches, results, send, late = _cancelled_execute_case()
    # Pre-fix the result observer saw ZERO records: the flight never
    # settled and the fragment watch held it forever.
    assert len(dispatches) == 1
    assert len(results) == 1
    assert results[0]["state"] == "cancelled"
    assert results[0]["turn_id"] == dispatches[0]["turn_id"]
    # The shielded send still landed and filed its late result for
    # the delivery watch's ordinary late channel — the cancellation
    # settle does not swallow the real answer.
    assert len(late) == 1
    assert late[0]["state"] == "answered"
    # Worker side: the settled flight unblocks recovery of a suspect
    # that landed during it.
    state = _new_fragment_watch()
    _fragment_flight_started(
        state, dispatches[0]["turn_id"], dispatches[0]["request"], 100.0)
    _fragment_user_final(
        state, "And how many open positions are there?", 110.0)
    _fragment_flight_settled(state, results[0]["turn_id"])
    due = _fragment_recovery_due(state, 121.0)
    assert [s["text"] for s in due] == [
        "And how many open positions are there?"]


def test_cancelled_execute_is_not_cached():
    import friday.voice.brain_bridge as bb
    from friday.voice.brain_bridge import VoiceBrainBridge

    async def _case():
        # fail_first: the cancelled send never lands, so no late
        # result is filed and nothing is cached — a re-issue must
        # send again. (Without fail_first the late "answered" would
        # legitimately be reused under the FRD-011 window; that
        # reuse is the designed behaviour, not the property pinned
        # here.)
        send = _BlockingSend(fail_first=True)
        bridge = VoiceBrainBridge()
        bridge._send = send
        task = asyncio.ensure_future(
            bridge.execute("What is the Stratex balance?"))
        await asyncio.sleep(0.2)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        send.released.set()
        await asyncio.sleep(0.2)
        assert bb.pop_late_results() == []
        # A re-issue must send again — the cancelled outcome was
        # never cached as the turn's answer.
        result = await bridge.execute("What is the Stratex balance?")
        assert result["state"] == "answered"
        return send

    send = _run(_case())
    assert send.calls == [
        "What is the Stratex balance?",
        "What is the Stratex balance?",
    ]


def test_completed_execute_still_settles_exactly_once():
    from friday.voice.brain_bridge import VoiceBrainBridge

    async def _case():
        results = []
        bridge = VoiceBrainBridge(result_observer=results.append)

        async def _send(client, text):
            return {"state": "answered", "spoken_reply": "Done."}

        bridge._send = _send
        result = await bridge.execute("What is the Stratex balance?")
        assert result["state"] == "answered"
        return results

    results = _run(_case())
    assert len(results) == 1
    assert results[0]["state"] == "answered"


def test_cancelled_execute_during_fragment_guard_hold_settles():
    # The guard's settle window (up to 3.5 s of sleeps) is a second
    # cancellation point after the flight-start notification: cancelling
    # there must settle too, not strand the flight.
    import friday.voice.brain_bridge as bb
    from friday.voice.brain_bridge import VoiceBrainBridge

    async def _case():
        dispatches, results = [], []
        bridge = VoiceBrainBridge(
            dispatch_observer=dispatches.append,
            result_observer=results.append,
            turn_transcript_provider=lambda: ("Friday remember this", 1),
        )
        # Remember-class, ungrounded in the supplied turn text: the
        # guard holds for its settle window.
        task = asyncio.ensure_future(
            bridge.execute("Remember this: my favorite color is teal"))
        await asyncio.sleep(0.3)
        assert len(dispatches) == 1
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        else:
            raise AssertionError("cancelled execute() must raise")
        return dispatches, results

    dispatches, results = _run(_case())
    assert len(results) == 1
    assert results[0]["state"] == "cancelled"
    assert results[0]["turn_id"] == dispatches[0]["turn_id"]


# ---------------------------------------------------------------------------
# TASK-VOI-043 (d): no arbitrary speech cancellation. The trigger is
# server-side — Gemini emits `interrupted` on start of user activity
# while activity_handling is START_OF_ACTIVITY_INTERRUPTS; the plugin
# turns it into input_speech_started, AgentActivity interrupts the
# speech unconditionally, and SpeechHandle force-cancels it after a
# hardcoded 5.0 s wind-down (livekit-agents 1.8.11 speech_handle.py)
# — a wind-down a bridge call in flight can never meet. The worker
# cannot gate the interrupt per turn (it fires before any transcript
# exists; the local knobs are inert under realtime_llm), so the
# server-side switch is flipped to NO_INTERRUPTION: her response is
# never cut by user activity, and a new turn is still transcribed,
# finalized and answered after she finishes — no turn is lost.
# The behavioural pins live where the AAD contract lives,
# test_voice_noise_interruption_voi032.py (default NO_INTERRUPTION,
# env restores barge-in, unknown value falls back); this file pins
# only the wiring below.
# ---------------------------------------------------------------------------

def test_worker_wiring_source_pins_voi043():
    src = (
        Path(__file__).resolve().parents[1]
        / "src" / "friday" / "voice" / "livekit_worker.py"
    ).read_text()
    assert "activity_handling=_activity_handling()" in src
    assert "FRIDAY_VOICE_AAD_ACTIVITY_HANDLING" in src
    assert "NO_INTERRUPTION" in src
    bridge_src = (
        Path(__file__).resolve().parents[1]
        / "src" / "friday" / "voice" / "brain_bridge.py"
    ).read_text()
    assert '"cancelled"' in bridge_src
    assert "_settle_once" in bridge_src
