"""TASK-VOI-022 — per-build input evidence (lifecycle diagnosis).

The lifecycle diagnosis (2026-11-18; ~/workspace/voice-lifecycle-diag,
issue #35 comment 6983117421) localized the deaf-rebuild defect (D1)
to the rtc AudioStream creation/delivery boundary in a process
already degraded by the D2 wedge substrate. Two sub-hypotheses
remain: H1a (an AudioStream created after degradation onset is dead
on creation in the FFI core) vs H1b (the rebuilt RoomIO's async
_init_task never links — sess.start() does not await linking).

FIX.md §3 specifies the hardening that makes the next occurrence
self-report: pure instrumentation, no behaviour change. These tests
pin it:

- ``_owner_audio_publications``: the owner participant's audio
  publications from room state (source, sid, subscription state) —
  owner rule, audio only, best-effort against broken room state;
- ``_journal_owner_audio_publications``: exactly one INFO line per
  session start, rebuilds included, in the FIX.md format
  "session build N: owner audio publications: [...]";
- ``_input_forward_dead``: the compound signature — publication
  present + this session's F2 counters all zero + the job's energy
  monitor saw energy within the last ~10 s — and NOT on a session
  whose input accepted the track (any counter moved), a silent
  track (no recent energy), no publication, or unknown counters;
- ``_check_input_forward``: the one-shot ~5 s check WARNINGs once
  per build ("input forward dead on build N ... H1a/H1b"), never
  twice for the same build, never for a superseded build, and
  re-arms for the rebuild's fresh start stamp;
- entrypoint shape: _start journals + arms the check AFTER the
  session_started_ts stamp, for every session it starts.
"""

import asyncio
import inspect
import logging
import sys
import time
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from friday.voice import livekit_worker as w  # noqa: E402


class _FakeSession:
    pass


def _pub(kind=1, source=2, sid="TR_audio", subscribed=True):
    return SimpleNamespace(kind=kind, source=source, sid=sid,
                           subscribed=subscribed)


def _participant(identity, pubs):
    return SimpleNamespace(
        identity=identity,
        track_publications={p.sid: p for p in pubs},
    )


def _room(*participants):
    return SimpleNamespace(
        remote_participants={p.identity: p for p in participants})


def _owner_room():
    return _room(_participant("owner-abc", [_pub()]))


def _watch(**overrides):
    watch = w._new_input_watch()
    watch.update(overrides)
    return watch


def _zero_counters(session, label="session build 2"):
    counters = w._new_frame_counters(label)
    w._register_frame_counters(session, counters)
    return counters


def _drop_counters(session):
    w._FRAME_COUNTERS.pop(id(session), None)


# ---------------------------------------------------------------------------
# _owner_audio_publications
# ---------------------------------------------------------------------------


def test_publications_snapshot_carries_source_sid_and_state(monkeypatch):
    monkeypatch.setattr(
        w, "_rtc", SimpleNamespace(TrackKind=SimpleNamespace(KIND_AUDIO=1)))
    room = _room(
        _participant("owner-abc", [
            _pub(kind=1, source=2, sid="TR_mic", subscribed=True),
            _pub(kind=2, source=1, sid="TR_cam", subscribed=True),
        ]),
        _participant("guest-1", [
            _pub(kind=1, source=2, sid="TR_guest", subscribed=True),
        ]),
    )
    pubs = w._owner_audio_publications(room)
    # Owner only, audio only: the camera publication and the
    # guest's microphone are not the owner's audio evidence.
    assert pubs == [{"source": 2, "sid": "TR_mic", "subscribed": True}]


def test_publications_snapshot_accepts_the_string_kind_shape(monkeypatch):
    monkeypatch.setattr(w, "_rtc", None)
    room = _room(_participant("owner-abc", [_pub(kind="audio")]))
    assert len(w._owner_audio_publications(room)) == 1


def test_publications_snapshot_empty_shapes():
    assert w._owner_audio_publications(_room()) == []
    assert w._owner_audio_publications(None) == []
    assert w._owner_audio_publications(_room(
        _participant("guest-1", [_pub()]))) == []
    assert w._owner_audio_publications(_room(
        _participant("owner-abc", []))) == []


def test_publications_snapshot_survives_broken_room_state():
    class _Broken:
        @property
        def track_publications(self):
            raise RuntimeError("room state gone")

    room = SimpleNamespace(remote_participants={"owner-abc": _Broken()})
    assert w._owner_audio_publications(room) == []


# ---------------------------------------------------------------------------
# _journal_owner_audio_publications — one line per build
# ---------------------------------------------------------------------------


def test_journal_line_per_build_including_rebuilds(caplog):
    room = _owner_room()
    with caplog.at_level(logging.INFO, logger="friday.voice"):
        w._journal_owner_audio_publications(room, "session build 1")
        w._journal_owner_audio_publications(room, "session build 2")
    lines = [r.getMessage() for r in caplog.records]
    build1 = [ln for ln in lines if "session build 1:" in ln]
    build2 = [ln for ln in lines if "session build 2:" in ln]
    assert len(build1) == 1 and len(build2) == 1
    assert "owner audio publications: [" in build1[0]
    assert "source=2" in build1[0]
    assert "sid=TR_audio" in build1[0]
    assert "subscribed=True" in build1[0]


def test_journal_line_with_no_publications_is_an_empty_list(caplog):
    with caplog.at_level(logging.INFO, logger="friday.voice"):
        pubs = w._journal_owner_audio_publications(_room(), "session build 3")
    assert pubs == []
    lines = [r.getMessage() for r in caplog.records]
    assert any("session build 3: owner audio publications: []" in ln
               for ln in lines)


# ---------------------------------------------------------------------------
# _input_forward_dead — the compound signature
# ---------------------------------------------------------------------------


def _counters(**overrides):
    counters = w._new_frame_counters("session build 2")
    counters.update(overrides)
    return counters


def test_signature_fires_on_publication_energy_and_zero_counters():
    watch = _watch(last_energy_ts=100.0)
    pubs = [{"source": 2, "sid": "TR_audio", "subscribed": True}]
    assert w._input_forward_dead(watch, _counters(), pubs, 105.0) is True
    # The window edge still counts as "in the last ~10 s".
    assert w._input_forward_dead(watch, _counters(), pubs, 110.0) is True


def test_signature_never_fires_once_a_track_is_accepted():
    # Any hop counting a frame means the session's input accepted
    # the track — the forward is alive by definition.
    watch = _watch(last_energy_ts=100.0)
    pubs = [{"source": 2, "sid": "TR_audio", "subscribed": True}]
    for key in ("activity_push_audio", "plugin_push_audio",
                "plugin_send_audio_events"):
        assert w._input_forward_dead(
            watch, _counters(**{key: 1}), pubs, 105.0) is False


def test_signature_never_fires_without_a_publication():
    watch = _watch(last_energy_ts=100.0)
    assert w._input_forward_dead(watch, _counters(), [], 105.0) is False


def test_signature_never_fires_on_unknown_counters():
    # A session whose counters could not be registered reads as
    # "unknown", not as a proven row of zeros.
    watch = _watch(last_energy_ts=100.0)
    pubs = [{"source": 2, "sid": "TR_audio", "subscribed": True}]
    assert w._input_forward_dead(watch, None, pubs, 105.0) is False


def test_signature_never_fires_without_recent_energy():
    # No energy at all: the owner simply has not spoken — the
    # false positive the energy condition exists to prevent.
    pubs = [{"source": 2, "sid": "TR_audio", "subscribed": True}]
    assert w._input_forward_dead(_watch(), _counters(), pubs, 105.0) is False
    # Energy 30 s ago is outside the ~10 s window: the track is
    # not demonstrably live NOW.
    watch = _watch(last_energy_ts=100.0)
    assert w._input_forward_dead(watch, _counters(), pubs, 130.0) is False


# ---------------------------------------------------------------------------
# _check_input_forward — the one-shot ~5 s check
# ---------------------------------------------------------------------------


def _warnings(caplog):
    return [r.getMessage() for r in caplog.records
            if r.levelno == logging.WARNING]


def test_check_warns_once_for_a_dead_forward(caplog):
    session = _FakeSession()
    _zero_counters(session)
    started = time.time()
    watch = _watch(session_started_ts=started, last_energy_ts=started)
    try:
        with caplog.at_level(logging.WARNING, logger="friday.voice"):
            asyncio.run(w._check_input_forward(
                _owner_room(), session, watch, started,
                "session build 2", delay_s=0.05))
            # A second check for the SAME build must not re-fire.
            asyncio.run(w._check_input_forward(
                _owner_room(), session, watch, started,
                "session build 2", delay_s=0.05))
    finally:
        _drop_counters(session)
    lines = _warnings(caplog)
    assert len(lines) == 1
    assert "input forward dead on session build 2" in lines[0]
    assert "owner publication present, monitor sees energy" in lines[0]
    assert "session counters 0" in lines[0]
    assert "H1a/H1b" in lines[0]
    assert watch["input_forward_warned_for"] == started


def test_check_stays_silent_when_a_track_is_accepted_in_time(caplog):
    session = _FakeSession()
    counters = _zero_counters(session)
    started = time.time()
    watch = _watch(session_started_ts=started, last_energy_ts=started)

    async def main():
        task = asyncio.ensure_future(w._check_input_forward(
            _owner_room(), session, watch, started,
            "session build 2", delay_s=0.3))
        await asyncio.sleep(0.05)
        # A frame crosses hop 1 inside the window: the session
        # accepted the track, so the check must not fire.
        counters["activity_push_audio"] += 1
        await task

    try:
        with caplog.at_level(logging.WARNING, logger="friday.voice"):
            asyncio.run(main())
    finally:
        _drop_counters(session)
    assert _warnings(caplog) == []
    assert watch["input_forward_warned_for"] is None


def test_check_stays_silent_for_a_superseded_build(caplog):
    # The ladder rebuilt before this build's check woke: the stale
    # check reads the NEW build's start stamp and stands down.
    session = _FakeSession()
    _zero_counters(session)
    started = time.time()
    watch = _watch(session_started_ts=started + 500.0,
                   last_energy_ts=started)
    try:
        with caplog.at_level(logging.WARNING, logger="friday.voice"):
            asyncio.run(w._check_input_forward(
                _owner_room(), session, watch, started,
                "session build 2", delay_s=0.05))
    finally:
        _drop_counters(session)
    assert _warnings(caplog) == []


def test_check_rearms_for_the_rebuild(caplog):
    session = _FakeSession()
    _zero_counters(session)
    first = time.time()
    watch = _watch(session_started_ts=first, last_energy_ts=first)
    try:
        with caplog.at_level(logging.WARNING, logger="friday.voice"):
            asyncio.run(w._check_input_forward(
                _owner_room(), session, watch, first,
                "session build 2", delay_s=0.05))
            # The rebuild: a fresh session object, fresh counters,
            # a fresh start stamp — the check arms again.
            session2 = _FakeSession()
            _zero_counters(session2, "session build 3")
            second = time.time()
            watch["session_started_ts"] = second
            watch["last_energy_ts"] = second
            try:
                asyncio.run(w._check_input_forward(
                    _owner_room(), session2, watch, second,
                    "session build 3", delay_s=0.05))
            finally:
                _drop_counters(session2)
    finally:
        _drop_counters(session)
    lines = _warnings(caplog)
    assert len(lines) == 2
    assert "input forward dead on session build 2" in lines[0]
    assert "input forward dead on session build 3" in lines[1]
    assert watch["input_forward_warned_for"] == second


def test_check_stays_silent_without_a_publication(caplog):
    session = _FakeSession()
    _zero_counters(session)
    started = time.time()
    watch = _watch(session_started_ts=started, last_energy_ts=started)
    try:
        with caplog.at_level(logging.WARNING, logger="friday.voice"):
            asyncio.run(w._check_input_forward(
                _room(), session, watch, started,
                "session build 2", delay_s=0.05))
    finally:
        _drop_counters(session)
    assert _warnings(caplog) == []


# ---------------------------------------------------------------------------
# Entrypoint source shape: _start journals + arms the check per build
# ---------------------------------------------------------------------------


def _start_src() -> str:
    src = inspect.getsource(w.entrypoint)
    start_at = src.index("async def _start")
    next_at = src.index("async def _greet_when_ready")
    return src[start_at:next_at]


def test_start_journals_and_arms_the_check_after_the_stamp():
    src = _start_src()
    stamp_at = src.index('input_watch["session_started_ts"] = time.time()')
    journal_at = src.index("_journal_owner_audio_publications(ctx.room")
    arm_at = src.index("_check_input_forward(")
    # The stamp is the check's baseline: both instrumentation
    # calls land after it, inside _start, for every session.
    assert stamp_at < journal_at < arm_at
    assert "input_forward_tasks.add(_fwd_task)" in src


def test_watch_carries_the_warned_for_marker():
    assert w._new_input_watch()["input_forward_warned_for"] is None
