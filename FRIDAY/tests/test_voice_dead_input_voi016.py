"""TASK-VOI-016 — the deaf window + the dead-input watchdog trigger.

FRD-005 re-run #10d (2026-11-17; diagnosis in
~/workspace/voice-session-diag, issue #35 comment 6944904999) failed
in a class the VOI-003/004 watchdog cannot see:

- VOI-014's greeting settle-hold kept sess.start() behind the
  greeting's stretched playback: join -> session able to hear took
  21.1 s, and the delegation utterance played 0.3 s before RoomIO
  linked was dropped by construction. A human caller's first
  sentence dies identically — no transcript, no turn, no error.
- Gemini then received NO audio in six consecutive sessions (1008
  'client inactivity' every ~122 s): the input established broken
  under a load peak is never rebuilt (plugin reconnects replace
  only the websocket), and the watchdog's triggers all need a
  transcript or an unrecoverable/classified error.

These tests pin the fix:

- the ready path starts the session WITHOUT awaiting the greeting
  settlement (the hold is gone from the entrypoint);
- the greeting line is gated on the session-listening event,
  bounded — it fires after the gate call, and the gate opens from
  _start / the listening state transition;
- ``_frame_rms`` / the energy monitor: loud owner-track frames
  stamp the watch, silent ones do not, and a broken stream
  constructor ends the monitor quietly;
- ``_dead_input_verdict``: fires on energy + zero transcripts +
  an old-enough session in front of the owner — and NOT on a
  silent room, a working STT, a young session, or twice for the
  same session;
- ``_note_inactivity_close`` / ``_is_inactivity_close``: each
  error record counts once, only the 1008-inactivity signature
  counts, and the watchdog treats the Kth consecutive close as
  session death (source shape).
"""

import asyncio
import inspect
import sys
import time
from array import array
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from friday.voice import livekit_worker as w  # noqa: E402


def _pcm(amplitude: int, n: int = 480) -> bytes:
    return array("h", [amplitude] * n).tobytes()


def _watch(**overrides):
    watch = w._new_input_watch()
    watch.update(overrides)
    return watch


# ---------------------------------------------------------------------------
# _frame_rms
# ---------------------------------------------------------------------------


def test_frame_rms_silence_is_zero():
    assert w._frame_rms(_pcm(0)) == 0.0
    assert w._frame_rms(b"") == 0.0
    assert w._frame_rms(None) == 0.0
    assert w._frame_rms(b"\x01") == 0.0  # sub-sample input


def test_frame_rms_constant_amplitude_is_exact():
    assert w._frame_rms(_pcm(1000)) == 1000.0
    assert w._frame_rms(_pcm(-1000)) == 1000.0


def test_frame_rms_odd_length_truncates_cleanly():
    data = _pcm(500, 10) + b"\xff"
    assert w._frame_rms(data) == 500.0


# ---------------------------------------------------------------------------
# The energy monitor (fake rtc): loud frames stamp, silence does not
# ---------------------------------------------------------------------------


class _FakeStream:
    def __init__(self, frames):
        self._frames = frames

    def __aiter__(self):
        return self._gen()

    async def _gen(self):
        for data in self._frames:
            yield SimpleNamespace(frame=SimpleNamespace(data=data))


def _fake_rtc(frames=None, boom=False):
    def _audio_stream(track, **_kw):
        if boom:
            raise RuntimeError("stream refused")
        return _FakeStream(frames or [])

    return SimpleNamespace(
        AudioStream=_audio_stream,
        TrackKind=SimpleNamespace(KIND_AUDIO=1),
    )


def test_monitor_stamps_energy_for_loud_frames(monkeypatch):
    monkeypatch.setattr(w, "_rtc", _fake_rtc([_pcm(0), _pcm(1500), _pcm(0)]))
    watch = _watch()
    asyncio.run(w._monitor_input_energy(object(), watch))
    assert watch["last_energy_ts"] is not None


def test_monitor_ignores_silence_and_below_floor(monkeypatch):
    # Amplitude 100 -> RMS 100, below the 200 floor: a muted or
    # empty track must never read as "the owner is speaking".
    monkeypatch.setattr(w, "_rtc", _fake_rtc([_pcm(0), _pcm(100)]))
    watch = _watch()
    asyncio.run(w._monitor_input_energy(object(), watch))
    assert watch["last_energy_ts"] is None


def test_monitor_survives_a_refused_stream(monkeypatch):
    monkeypatch.setattr(w, "_rtc", _fake_rtc(boom=True))
    watch = _watch()
    asyncio.run(w._monitor_input_energy(object(), watch))  # no raise
    assert watch["last_energy_ts"] is None


def test_monitor_without_rtc_is_a_noop(monkeypatch):
    monkeypatch.setattr(w, "_rtc", None)
    watch = _watch()
    asyncio.run(w._monitor_input_energy(object(), watch))
    assert watch["last_energy_ts"] is None


# ---------------------------------------------------------------------------
# _is_inactivity_close / _note_inactivity_close
# ---------------------------------------------------------------------------

# The #10d close, in the shape _error_event_details records it
# (repr of the plugin's error model + the inner websocket error).
_INACTIVITY_TEXT = (
    "RealtimeModelError(type='realtime_model_error') | "
    "WebSocketClosedError: received 1008 (session closed due to "
    "client inactivity); then sent 1008 (session closed due to "
    "client inactivity)"
)


def test_inactivity_signature_matches_the_10d_close():
    assert w._is_inactivity_close(_INACTIVITY_TEXT) is True


def test_inactivity_signature_rejects_other_errors():
    assert w._is_inactivity_close("TimeoutError: timed out during opening handshake") is False
    # A 1008 that is not the inactivity timer must not count.
    assert w._is_inactivity_close("received 1008 (policy violation)") is False
    assert w._is_inactivity_close("") is False
    assert w._is_inactivity_close(None) is False


def test_note_inactivity_close_counts_each_record_once():
    watch = _watch()
    err = {"ts": 100.0, "text": _INACTIVITY_TEXT, "recoverable": True}
    # The watchdog polls the same record every 5 s — it counts once.
    assert w._note_inactivity_close(watch, err) == 1
    assert w._note_inactivity_close(watch, err) == 1
    assert w._note_inactivity_close(watch, err) == 1
    # A NEW record (the plugin's retry closed again) is the second
    # consecutive close.
    err2 = {"ts": 222.0, "text": _INACTIVITY_TEXT, "recoverable": True}
    assert w._note_inactivity_close(watch, err2) == 2


def test_note_inactivity_close_ignores_other_errors():
    watch = _watch()
    err = {"ts": 100.0, "text": "APIConnectionError: failed to connect",
           "recoverable": None}
    assert w._note_inactivity_close(watch, err) == 0
    # ...but the record is still marked counted, so the next poll
    # does not recount it either way.
    assert w._note_inactivity_close(watch, err) == 0
    assert w._note_inactivity_close(watch, None) == 0


# ---------------------------------------------------------------------------
# _dead_input_verdict
# ---------------------------------------------------------------------------


def test_dead_input_fires_on_energy_without_transcripts():
    # Session started at 100, owner spoke (energy) at 110, still no
    # transcript of any kind at 130 (age 30 >= the 25 s threshold).
    watch = _watch(session_started_ts=100.0, last_energy_ts=110.0)
    assert w._dead_input_verdict(
        watch, 130.0, owner_present=True, session_live=True
    ) is True


def test_dead_input_never_fires_in_a_silent_room():
    # No energy at all: the owner simply has not spoken yet. This
    # is the false-positive the energy condition exists to prevent.
    watch = _watch(session_started_ts=100.0)
    assert w._dead_input_verdict(
        watch, 1000.0, owner_present=True, session_live=True
    ) is False


def test_dead_input_ignores_energy_from_a_previous_session():
    # Energy at 90 belongs to the session the ladder already
    # replaced; the new session (started 100) has heard nothing.
    watch = _watch(session_started_ts=100.0, last_energy_ts=90.0)
    assert w._dead_input_verdict(
        watch, 1000.0, owner_present=True, session_live=True
    ) is False


def test_dead_input_never_fires_when_transcripts_flow():
    # An interim transcript in this session's life is proof the
    # forward works — even if no turn has completed yet.
    watch = _watch(
        session_started_ts=100.0, last_energy_ts=110.0,
        last_transcript_ts=112.0,
    )
    assert w._dead_input_verdict(
        watch, 1000.0, owner_present=True, session_live=True
    ) is False


def test_dead_input_waits_for_the_threshold():
    watch = _watch(session_started_ts=100.0, last_energy_ts=105.0)
    assert w._dead_input_verdict(
        watch, 124.9, owner_present=True, session_live=True
    ) is False
    assert w._dead_input_verdict(
        watch, 125.0, owner_present=True, session_live=True
    ) is True


def test_dead_input_requires_owner_and_a_live_session():
    watch = _watch(session_started_ts=100.0, last_energy_ts=110.0)
    assert w._dead_input_verdict(
        watch, 1000.0, owner_present=False, session_live=True
    ) is False
    assert w._dead_input_verdict(
        watch, 1000.0, owner_present=True, session_live=False
    ) is False


def test_dead_input_fires_once_per_session_start():
    watch = _watch(
        session_started_ts=100.0, last_energy_ts=110.0,
        fired_for_session=100.0,
    )
    assert w._dead_input_verdict(
        watch, 1000.0, owner_present=True, session_live=True
    ) is False
    # The rebuild's fresh start stamp re-arms it.
    watch["session_started_ts"] = 2000.0
    watch["last_energy_ts"] = 2010.0
    assert w._dead_input_verdict(
        watch, 2030.0, owner_present=True, session_live=True
    ) is True


def test_input_watch_is_per_job():
    a = w._new_input_watch()
    b = w._new_input_watch()
    a["inactivity_closes"] = 2
    assert b["inactivity_closes"] == 0


# ---------------------------------------------------------------------------
# _await_session_listening — the greeting gate's bounded wait
# ---------------------------------------------------------------------------


def test_listening_gate_opens_when_already_listening():
    async def main():
        event = asyncio.Event()
        event.set()
        started = time.time()
        heard = await w._await_session_listening(event, timeout_s=5.0)
        return heard, time.time() - started

    heard, elapsed = asyncio.run(main())
    assert heard is True
    assert elapsed < 1.0


def test_listening_gate_opens_when_listening_lands_during_the_wait():
    async def main():
        event = asyncio.Event()

        async def setter():
            await asyncio.sleep(0.1)
            event.set()

        task = asyncio.ensure_future(setter())
        heard = await w._await_session_listening(event, timeout_s=5.0)
        await task
        return heard

    assert asyncio.run(main()) is True


def test_listening_gate_expires_at_the_cap_and_the_line_plays_anyway():
    async def main():
        event = asyncio.Event()
        started = time.time()
        heard = await w._await_session_listening(event, timeout_s=0.2)
        return heard, time.time() - started

    heard, elapsed = asyncio.run(main())
    assert heard is False  # caller plays the line regardless
    assert elapsed < 2.0  # bounded — never a new settle-hold


def test_listening_gate_without_an_event_is_closed():
    assert asyncio.run(w._await_session_listening(None, timeout_s=0.1)) is False


# ---------------------------------------------------------------------------
# Entrypoint source shape: gate ordering, gate setters, watchdog wiring
# ---------------------------------------------------------------------------


def _entry_src() -> str:
    return inspect.getsource(w.entrypoint)


def test_early_line_waits_at_the_gate_before_playing():
    src = _entry_src()
    line_at = src.index("async def _play_early_greeting_line")
    launch_at = src.index('early_greeting["task"] = asyncio.ensure_future(')
    line_src = src[line_at:launch_at]
    gate_at = line_src.index("_await_session_listening(")
    attempted_at = line_src.index('greeting_state["attempted"] = True')
    play_at = line_src.index('_play_fixed_line(ctx.room, "greeting")')
    # The gate is awaited before the line is attempted or played.
    assert gate_at < attempted_at < play_at


def test_gate_opens_from_start_and_from_the_listening_transition():
    src = _entry_src()
    # _start (sess.start() returned) and the agent_state handler.
    assert src.count("session_listening.set()") >= 2
    assert 'input_watch["session_started_ts"] = time.time()' in src


def test_watchdog_carries_the_dead_input_trigger():
    src = _entry_src()
    watch_at = src.index("async def _watch_turns")
    deliver_at = src.index("async def _deliver_memory_when_ready")
    watch_src = src[watch_at:deliver_at]
    assert "_note_inactivity_close(input_watch, err)" in watch_src
    assert "_INACTIVITY_CLOSE_LIMIT" in watch_src
    assert "_dead_input_verdict(" in watch_src
    # The trigger runs the EXISTING ladder — no second recovery path.
    assert "await _recover(pending_text)" in watch_src
    assert 'input_watch["fired_for_session"]' in watch_src


def test_owner_tracks_get_the_energy_monitor():
    src = _entry_src()
    assert "_monitor_input_energy(track, input_watch)" in src
    assert 'ctx.room.on("track_unsubscribed", _on_track_unsubscribed)' in src


def test_transcribed_handler_records_proof_of_life():
    src = _entry_src()
    assert 'input_watch["last_transcript_ts"] = time.time()' in src
    assert 'input_watch["inactivity_closes"] = 0' in src
