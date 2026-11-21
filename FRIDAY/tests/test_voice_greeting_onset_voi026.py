"""TASK-VOI-026: greeting-onset decomposition instrumentation.

The greeting misses the 8 s bar even on a calm box (11.3 s / 17.0 s
in the VOI-024 A/B arms, both arms) and the existing journal lines
cannot say which leg owns the time. This task adds the missing
stage timestamps and one decomposition journal line; these tests pin:

- ``_new_greeting_onset`` / ``_stage_diff`` / ``_format_greeting_onset``:
  the decomposition line's legs, '-' for stages that never ran, and
  the gate outcome wording (LISTENING vs cap).
- The listening-gate cap's semantics: ``_await_session_listening`` is
  an ``asyncio.wait_for`` timeout, so the 5 s cap fires only when the
  job loop iterates — a blocked loop resolves it late. That is the
  prime suspect for the 11.3 s / 17.0 s onsets (re-run #3's
  page-fault storm gave the ready task no effective loop time for
  ~21 s), and the decomposition line exists to prove or kill it in
  production.
- Entrypoint wiring (source shape): the build/start stamps and the
  decomposition log call are present where the greeting path runs.
"""
import asyncio
import inspect
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from friday.voice import livekit_worker as w  # noqa: E402


def _full_timings():
    return {
        "job_start": 100.0,
        "connected": 100.5,
        "key_ready": 100.6,
        "participant_seen": 100.7,
        "gate_decided": 105.8,
        "gate_heard": True,
        "gate_wait_s": 5.1,
        "first_audio": 105.9,
        "build_start": 100.6,
        "build_done": 102.0,
        "start_done": 105.8,
    }


# ---------- stage dict + legs ----------


def test_new_greeting_onset_starts_empty():
    timings = w._new_greeting_onset()
    assert timings["job_start"] is None
    assert timings["connected"] is None
    assert timings["key_ready"] is None
    assert timings["participant_seen"] is None
    assert timings["gate_decided"] is None
    assert timings["gate_heard"] is None
    assert timings["gate_wait_s"] is None
    assert timings["first_audio"] is None
    assert timings["build_start"] is None
    assert timings["build_done"] is None
    assert timings["start_done"] is None


def test_stage_diff_both_set():
    timings = {"a": 10.0, "b": 12.5}
    assert w._stage_diff(timings, "b", "a") == "2.50s"


def test_stage_diff_missing_stage_is_dash():
    assert w._stage_diff({"a": 10.0}, "b", "a") == "-"
    assert w._stage_diff({"b": 12.5}, "b", "a") == "-"
    assert w._stage_diff({}, "b", "a") == "-"


# ---------- formatter ----------


def test_format_greeting_onset_full_stages():
    line = w._format_greeting_onset(_full_timings())
    assert line == (
        "VOICE greeting onset decomposition (TASK-VOI-026): "
        "job-to-connect 0.50s, connect-to-key 0.10s, "
        "key-to-participant 0.10s, participant-to-gate 5.10s, "
        "gate LISTENING after 5.10s, connect-to-first-audio 5.40s"
    )


def test_format_greeting_onset_gate_cap_wording():
    timings = _full_timings()
    timings["gate_heard"] = False
    line = w._format_greeting_onset(timings)
    assert "gate cap after 5.10s" in line


def test_format_greeting_onset_missing_stages_are_dashes():
    timings = {"connected": 100.5, "first_audio": 105.9}
    line = w._format_greeting_onset(timings)
    assert line == (
        "VOICE greeting onset decomposition (TASK-VOI-026): "
        "job-to-connect -, connect-to-key -, "
        "key-to-participant -, participant-to-gate -, "
        "gate - after -, connect-to-first-audio 5.40s"
    )


def test_format_greeting_onset_no_connect_stamp():
    assert w._format_greeting_onset({}) == (
        "VOICE greeting onset decomposition (TASK-VOI-026): no connect stamp"
    )


# ---------- gate-cap semantics: loop-time, not wall-clock ----------


def test_listening_gate_cap_fires_late_on_blocked_loop():
    """The 5 s cap is an asyncio.wait_for timeout: it resolves only
    when the loop iterates. Block the loop thread for 2 s with a
    0.5 s cap and the waiter returns at ~2.05 s, not 0.5 s. This is
    the mechanism the decomposition line must test in production:
    on the swapped voice host, sess.start()'s page-fault storm
    blocks the loop the same way and the greeting fires when the
    session starts, not at the cap."""
    event = asyncio.Event()

    async def main():
        t0 = time.perf_counter()
        gate_task = asyncio.create_task(
            w._await_session_listening(event, 0.5)
        )
        await asyncio.sleep(0.05)  # let the gate task start waiting
        time.sleep(2.0)  # synchronous block: the loop cannot iterate
        heard = await gate_task
        return heard, time.perf_counter() - t0

    heard, elapsed = asyncio.run(main())
    assert heard is False  # the event was never set; the cap expired
    assert elapsed > 1.5, f"cap resolved at {elapsed:.2f}s, not late"
    assert elapsed < 3.0, f"cap resolved at {elapsed:.2f}s, implausibly late"


def test_listening_gate_healthy_loop_contract():
    """Control: on a free loop the cap fires on time and a set event
    returns True promptly. (Each asyncio.run gets its own Event:
    an Event binds to the first loop that uses it.)"""

    async def main_cap():
        event = asyncio.Event()
        t0 = time.perf_counter()
        heard = await w._await_session_listening(event, 0.2)
        return heard, time.perf_counter() - t0

    heard, elapsed = asyncio.run(main_cap())
    assert heard is False
    assert elapsed < 1.0, f"cap resolved at {elapsed:.2f}s on a free loop"

    async def main_set():
        event = asyncio.Event()

        async def setter():
            await asyncio.sleep(0.1)
            event.set()

        setter_task = asyncio.create_task(setter())
        t0 = time.perf_counter()
        heard = await w._await_session_listening(event, 5.0)
        await setter_task
        return heard, time.perf_counter() - t0

    heard, elapsed = asyncio.run(main_set())
    assert heard is True
    assert elapsed < 1.0, f"set event resolved at {elapsed:.2f}s"


# ---------- entrypoint wiring (source shape) ----------


def test_entrypoint_stamps_greeting_onset_stages():
    src = inspect.getsource(w.entrypoint)
    assert 'greet_timing = _new_greeting_onset()' in src
    assert 'greet_timing["job_start"] = time.time()' in src
    assert 'greet_timing["connected"] = _t_connected' in src
    assert 'greet_timing["key_ready"] = _key_ready_at["ts"]' in src
    assert 'greet_timing["participant_seen"] = time.time()' in src
    assert 'greet_timing["gate_heard"] = bool(_gate_heard)' in src
    assert 'greet_timing["gate_decided"] = time.time()' in src
    assert 'greet_timing["first_audio"] = time.time()' in src
    assert 'greet_timing["build_start"] = time.time()' in src
    assert 'greet_timing["build_done"] = time.time()' in src
    assert 'greet_timing["start_done"] = time.time()' in src
    assert 'logger.info("%s", _format_greeting_onset(greet_timing))' in src
    # The session-started line now splits key-to-session-started
    # into its build and start legs.
    assert '_stage_diff(greet_timing, "build_done", "build_start")' in src
    assert '_stage_diff(greet_timing, "start_done", "build_done")' in src
