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
"""

import asyncio
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


def test_ladder_plan_gemini_is_pinned_pinned_groq():
    assert worker._ladder_plan("gemini") == ["gemini", "gemini", "groq"]
    assert worker._ladder_plan(None) == ["gemini", "gemini", "groq"]


def test_ladder_plan_groq_has_no_lower_rung():
    assert worker._ladder_plan("groq") == ["groq", "groq"]


def test_ladder_plan_never_moves_back_up():
    for kind in ("gemini", "groq", None, "anything"):
        plan = worker._ladder_plan(kind)
        assert plan[-1] == "groq" or set(plan) == {"groq"}
        if "groq" in plan and "gemini" in plan:
            last_gemini = len(plan) - 1 - plan[::-1].index("gemini")
            assert plan.index("groq") > last_gemini


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
            (False, "gemini did not complete the re-asked turn", 100.0),
            (True, "groq completed the re-asked turn", 12.0),
        ],
        calls,
    )
    report = _run(
        worker._run_recovery_ladder(
            worker._ladder_plan("gemini"), attempt,
            budget_s=300.0, rung_prove_s=100.0, now=clock,
        )
    )
    assert report["served"] == "groq"
    assert [c[0] for c in calls] == ["gemini", "gemini", "groq"]
    assert [s[1] for s in report["steps"]] == [False, False, True]
    assert report["elapsed"] == 152.0


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
        [(False, "fail 1", 30.0), (False, "fail 2", 30.0), (False, "fail 3", 30.0)],
        calls,
    )
    report = _run(
        worker._run_recovery_ladder(
            worker._ladder_plan("gemini"), attempt,
            budget_s=300.0, rung_prove_s=100.0, now=clock,
        )
    )
    assert report["served"] is None
    assert len(report["steps"]) == 3
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
            budget_s=150.0, rung_prove_s=100.0, now=clock,
        )
    )
    # rung 1 gets 100 s, rung 2 only the remaining 50 s, rung 3 never runs
    assert calls == [("gemini", 100.0), ("gemini", 50.0)]
    assert report["served"] is None
    assert len(report["steps"]) == 3
    assert "budget exhausted" in report["steps"][2][2]


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
