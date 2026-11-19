"""TASK-VOI-004 — watchdog rebuild-resilience ladder.

VOI-003's watchdog rebuilt a wedged session once and returned; in its
acceptance run 2 the rebuilt session itself died at the Gemini Live
opening handshake (session error: type='realtime_model_error',
error=TimeoutError('timed out during opening handshake'),
recoverable=False — journal 2026-11-14 22:27:13-15 IST) and nothing
recovered further. These tests pin the ladder that replaces the
single rebuild:

- provider-failure classification, calibrated on the real journal
  strings from that run (and on look-alike NON-provider strings that
  must not trigger a failover);
- error-event detail extraction (recoverable flag + text);
- the rung plan (pinned, pinned, one context-carrying Groq failover;
  the plan only ever moves down the provider chain);
- the ladder sequencer: rung ordering, first-success stop, and the
  single total elapsed budget shared by all rungs.

TASK-VOI-009 (2026-11-15): the Groq failover rung is REMOVED (owner:
"Gemini is the only AI for voice"). The plan tests below were converted
to the Gemini-only contract — two pinned Gemini rebuilds, no second
provider anywhere in the plan — and the sequencer tests re-scripted
for the two-rung plan. Classification and budget rules are unchanged.
"""

import asyncio
import inspect
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from friday.voice import livekit_worker as worker  # noqa: E402


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


# ---------------------------------------------------------------------------
# Provider-failure classification
# ---------------------------------------------------------------------------


def test_classify_run2_handshake_death_is_provider_failure():
    # The verbatim payload of the session error event that killed
    # VOI-003 acceptance run 2's rebuilt session (journal 22:27:15 IST).
    text = (
        "type='realtime_model_error' timestamp=1794675435.2991545 "
        "label='livekit.plugins.google.realtime.realtime_api.RealtimeModel' "
        "error=TimeoutError('timed out during opening handshake') "
        "recoverable=False"
    )
    assert worker._classify_provider_failure(text) is True


def test_classify_api_connection_error_is_provider_failure():
    text = "APIConnectionError: Failed to connect to Gemini Live (caused by TimeoutError)"
    assert worker._classify_provider_failure(text) is True


def test_classify_quota_and_availability_are_provider_failures():
    assert worker._classify_provider_failure("503 Service Unavailable") is True
    assert worker._classify_provider_failure(
        "Resource has been exhausted (e.g. check quota)."
    ) is True
    assert worker._classify_provider_failure("429 RESOURCE_EXHAUSTED") is True
    assert worker._classify_provider_failure(
        "websockets.exceptions.ConnectionClosedError: connection closed"
    ) is True


def test_classify_non_provider_errors_stay_local():
    # Look-alikes that must NOT tear down a session or trigger a
    # failover: interruptions, TTS terms, local misuse, slow memory.
    assert worker._classify_provider_failure("") is False
    assert worker._classify_provider_failure(None) is False
    assert worker._classify_provider_failure(
        "speech not done in time after interruption, cancelling the speech arbitrarily"
    ) is False
    assert worker._classify_provider_failure(
        "400 model_terms_required: orpheus TTS requires model terms acceptance"
    ) is False
    assert worker._classify_provider_failure("ValueError: invalid argument 'foo'") is False
    assert worker._classify_provider_failure("owner memory recall timed out") is False
    assert worker._classify_provider_failure("STTError: transcription produced no text") is False


# ---------------------------------------------------------------------------
# Error-event detail extraction
# ---------------------------------------------------------------------------


def test_error_event_details_realtime_model_error():
    inner = TimeoutError("timed out during opening handshake")
    err = SimpleNamespace(
        type="realtime_model_error", recoverable=False, error=inner
    )
    ev = SimpleNamespace(error=err)
    text, recoverable = worker._error_event_details(ev)
    assert recoverable is False
    assert "realtime_model_error" in text
    assert "timed out during opening handshake" in text
    # and the extracted text classifies as the provider failure it is
    assert worker._classify_provider_failure(text) is True


def test_error_event_details_bare_exception():
    ev = SimpleNamespace(error=ValueError("bad input"))
    text, recoverable = worker._error_event_details(ev)
    assert recoverable is None
    assert "bad input" in text
    assert worker._classify_provider_failure(text) is False


def test_error_event_details_event_level_recoverable():
    ev = SimpleNamespace(error=RuntimeError("boom"), recoverable=False)
    _text, recoverable = worker._error_event_details(ev)
    assert recoverable is False


def test_error_event_details_no_error_attribute():
    ev = SimpleNamespace()
    text, recoverable = worker._error_event_details(ev)
    assert recoverable is None
    assert isinstance(text, str) and text


# ---------------------------------------------------------------------------
# Ladder plan
# ---------------------------------------------------------------------------


def test_ladder_plan_is_two_pinned_gemini_rebuilds():
    # TASK-VOI-009: was pinned/pinned/Groq-failover before the removal.
    assert worker._ladder_plan("gemini") == ["gemini", "gemini"]
    assert worker._ladder_plan(None) == ["gemini", "gemini"]


def test_ladder_plan_has_no_second_provider():
    # The pre-VOI-009 plan for a Groq session was ["groq", "groq"];
    # there is no Groq session any more — every input gets the one
    # Gemini plan, and no plan may name any other provider.
    assert worker._ladder_plan("groq") == ["gemini", "gemini"]
    for kind in ("gemini", "groq", None, "anything"):
        assert "groq" not in worker._ladder_plan(kind)


def test_ladder_plan_never_leaves_gemini():
    # Was "never moves back up the provider chain"; with one provider
    # the stronger contract is: the plan never leaves Gemini at all.
    for kind in ("gemini", "groq", None, "anything"):
        plan = worker._ladder_plan(kind)
        assert set(plan) == {"gemini"}
        assert len(plan) == 2


# ---------------------------------------------------------------------------
# Ladder sequencer (fake clock + scripted attempts)
# ---------------------------------------------------------------------------


class _Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def _scripted_attempt(clock, outcomes, calls):
    async def attempt(kind, prove_s):
        calls.append((kind, prove_s))
        served, reason, consume = outcomes.pop(0)
        clock.t += consume
        return served, reason

    return attempt


def test_ladder_walks_the_plan_until_a_rung_serves():
    clock = _Clock()
    calls = []
    attempt = _scripted_attempt(
        clock,
        [
            (False, "gemini died on a provider failure: handshake", 40.0),
            (True, "gemini completed the re-asked turn", 12.0),
        ],
        calls,
    )
    report = _run(
        worker._run_recovery_ladder(
            worker._ladder_plan("gemini"), attempt,
            budget_s=300.0, rung_prove_s=100.0, now=clock,
        )
    )
    # TASK-VOI-009: the serving rung used to be the Groq failover; the
    # second pinned Gemini rebuild is now the last rung that can serve.
    assert report["served"] == "gemini"
    assert [c[0] for c in calls] == ["gemini", "gemini"]
    assert [s[1] for s in report["steps"]] == [False, True]
    assert report["elapsed"] == 52.0


def test_ladder_stops_at_first_success():
    clock = _Clock()
    calls = []
    attempt = _scripted_attempt(
        clock, [(True, "gemini completed the re-asked turn", 5.0)], calls
    )
    report = _run(
        worker._run_recovery_ladder(
            worker._ladder_plan("gemini"), attempt,
            budget_s=300.0, rung_prove_s=100.0, now=clock,
        )
    )
    assert report["served"] == "gemini"
    assert len(report["steps"]) == 1
    assert len(calls) == 1


def test_ladder_exhaustion_reports_every_rung():
    clock = _Clock()
    calls = []
    attempt = _scripted_attempt(
        clock,
        [(False, "fail 1", 30.0), (False, "fail 2", 30.0)],
        calls,
    )
    report = _run(
        worker._run_recovery_ladder(
            worker._ladder_plan("gemini"), attempt,
            budget_s=300.0, rung_prove_s=100.0, now=clock,
        )
    )
    assert report["served"] is None
    # TASK-VOI-009: two rungs is the whole ladder now (was three).
    assert len(report["steps"]) == 2
    assert all(not s[1] for s in report["steps"])


def test_ladder_total_budget_is_shared_and_binding():
    clock = _Clock()
    calls = []

    async def attempt(kind, prove_s):
        calls.append((kind, prove_s))
        clock.t += prove_s  # each rung burns its whole prove window
        return False, "prove window expired"

    report = _run(
        worker._run_recovery_ladder(
            worker._ladder_plan("gemini"), attempt,
            budget_s=90.0, rung_prove_s=100.0, now=clock,
        )
    )
    # TASK-VOI-009 (two-rung plan): rung 1's prove window is capped by
    # the shared budget (90 s, not the 100 s rung allowance) and burns
    # it all; rung 2 is then recorded as budget-exhausted without an
    # attempt. (Pre-removal this used a 150 s budget across 3 rungs.)
    assert calls == [("gemini", 90.0)]
    assert report["served"] is None
    assert len(report["steps"]) == 2
    assert "budget exhausted" in report["steps"][1][2]


def test_ladder_with_no_budget_runs_nothing():
    clock = _Clock()
    calls = []
    attempt = _scripted_attempt(clock, [(True, "served", 0.0)], calls)
    report = _run(
        worker._run_recovery_ladder(
            worker._ladder_plan("gemini"), attempt,
            budget_s=0.0, rung_prove_s=100.0, now=clock,
        )
    )
    assert calls == []
    assert report["served"] is None


# ---------------------------------------------------------------------------
# Env budget parsing
# ---------------------------------------------------------------------------


def test_env_float_parsing(monkeypatch):
    monkeypatch.setenv("FRIDAY_VOI004_TEST_X", "42.5")
    assert worker._env_float("FRIDAY_VOI004_TEST_X", 1.0) == 42.5
    monkeypatch.setenv("FRIDAY_VOI004_TEST_X", "not-a-number")
    assert worker._env_float("FRIDAY_VOI004_TEST_X", 1.0) == 1.0
    monkeypatch.setenv("FRIDAY_VOI004_TEST_X", "")
    assert worker._env_float("FRIDAY_VOI004_TEST_X", 7.0) == 7.0
    monkeypatch.delenv("FRIDAY_VOI004_TEST_X")
    assert worker._env_float("FRIDAY_VOI004_TEST_X", 3.0) == 3.0


def test_recovery_budgets_have_sane_defaults():
    assert worker._RECOVERY_BUDGET_S > worker._RUNG_PROVE_S > 0


# ---------------------------------------------------------------------------
# TASK-VOI-017 (F1): a rung is proven by a transcript or a completed
# turn — never by surviving the prove window.
# ---------------------------------------------------------------------------
# FRD-005 re-run #11: the ladder declared SUCCEEDED five times on
# rebuilt sessions that never transcribed a word, because a rung
# with no pending turn proved itself by surviving a ~20 s grace
# window. Each false success stopped the rebuilds a still-deaf
# session needed. These tests pin the new proof contract.


def test_rung_proven_pending_turn_requires_completion():
    assert worker._rung_proven(
        "what time is it", turn_completed=True, transcript_landed=False
    ) is True
    assert worker._rung_proven(
        "what time is it", turn_completed=False, transcript_landed=True
    ) is False
    assert worker._rung_proven(
        "what time is it", turn_completed=False, transcript_landed=False
    ) is False


def test_rung_proven_no_pending_turn_requires_a_transcript():
    # The re-run #11 regression pin: no pending turn + no transcript
    # (the session merely survived) is NOT proof, even when the
    # owner was audibly speaking (a transcript flag is what counts).
    assert worker._rung_proven(
        "", turn_completed=False, transcript_landed=False
    ) is False
    assert worker._rung_proven(
        "", turn_completed=False, transcript_landed=True
    ) is True
    # A stray completion timestamp with no pending turn proves
    # nothing on its own.
    assert worker._rung_proven(
        "", turn_completed=True, transcript_landed=False
    ) is False


def test_rung_unproven_reason_names_deaf_vs_silent():
    deaf = worker._rung_unproven_reason("gemini", energy_seen=True)
    assert "stayed deaf" in deaf
    assert "no user transcript" in deaf
    silent = worker._rung_unproven_reason("gemini", energy_seen=False)
    assert "unproven" in silent
    assert "silent room" in silent


def test_frames_flowed_reads_the_f2_counters():
    # TASK-VOI-023: any hop above zero means frames crossed the
    # forward; a row of zeros — or no registered counters at all —
    # does not. Unknown is not flowed: the energy-only criteria
    # then decide, unchanged.
    counters = worker._new_frame_counters("session build 2")
    assert worker._frames_flowed(counters) is False
    assert worker._frames_flowed(None) is False
    for key in ("activity_push_audio", "plugin_push_audio",
                "plugin_send_audio_events"):
        flowed = worker._new_frame_counters("session build 2")
        flowed[key] = 1
        assert worker._frames_flowed(flowed) is True


def test_rung_unproven_reason_counters_outrank_the_energy_estimate():
    # TASK-VOI-023, acceptance run #16's exact counters: build 2
    # received 356 frames and build 3 received 6,796, yet the
    # ladder declared both rungs failed as "silent room" because
    # the RMS energy monitor stamped nothing in the prove window.
    # Counters that flowed must win: the reason is the deaf one,
    # never silence, and it names the frame evidence.
    for frames in (356, 6796):
        counters = worker._new_frame_counters("session build 2")
        counters["activity_push_audio"] = frames
        counters["plugin_push_audio"] = frames
        counters["plugin_send_audio_events"] = frames - 1
        reason = worker._rung_unproven_reason(
            "gemini", energy_seen=False,
            frames_flowed=worker._frames_flowed(counters),
        )
        assert "stayed deaf" in reason
        assert "frames flowed" in reason
        assert "silent room" not in reason
    # With the monitor ALSO reporting energy, the counters still
    # name the evidence.
    reason = worker._rung_unproven_reason(
        "gemini", energy_seen=True, frames_flowed=True
    )
    assert "stayed deaf" in reason
    assert "frames flowed" in reason


def test_rung_unproven_reason_zero_counters_keep_the_energy_verdicts():
    # TASK-VOI-023: counters zero + no energy keeps the pre-fix
    # silent-room verdict, and counters zero + energy keeps the
    # pre-fix deaf verdict — the criterion changed only where
    # the counters actually flowed.
    counters = worker._new_frame_counters("session build 2")
    flowed = worker._frames_flowed(counters)
    assert flowed is False
    silent = worker._rung_unproven_reason(
        "gemini", energy_seen=False, frames_flowed=flowed
    )
    assert "unproven" in silent
    assert "silent room" in silent
    deaf = worker._rung_unproven_reason(
        "gemini", energy_seen=True, frames_flowed=flowed
    )
    assert "stayed deaf" in deaf
    assert "track energy was present" in deaf


def test_entrypoint_rungs_consult_the_frame_counters():
    # TASK-VOI-023 source shape: the rung's failure reason is
    # computed from the rung session's own counters, not the
    # energy estimate alone.
    src = inspect.getsource(worker.entrypoint)
    assert "_frames_flowed(_frame_counters_for(sess))" in src
    assert "frames_flowed=frames_flowed" in src


def test_entrypoint_rungs_judge_proof_via_rung_proven():
    src = inspect.getsource(worker.entrypoint)
    assert "_rung_proven(" in src
    assert "_rung_unproven_reason(" in src
    # The false-success sentence is gone from the entrypoint.
    assert "survived the grace window" not in src
