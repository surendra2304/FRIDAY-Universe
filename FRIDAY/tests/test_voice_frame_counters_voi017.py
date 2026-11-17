"""TASK-VOI-017 (F2): permanent frame-flow counters in the worker.

The frame-flow diagnosis (2026-11-17) found the deaf-session defect
class by counting frames at three hops with counters monkeypatched
into a reproduction: AgentActivity.push_audio (the session
forward), the Google plugin session's push_audio (the realtime
input), and the plugin's _send_client_event audio events (what
actually queued for the websocket). VOI-017 makes those counters
permanent worker instrumentation: every session built by
``_make_session`` carries a counters dict, and the counts are
journaled per session at session end and at watchdog firing, so the
next deaf session names its own dropping hop in production.

These tests pin: the registry + journal line, the audio-event
discriminator, the plugin/model wraps counting exactly the audio
path, the AgentActivity wrap attributing frames to the right
session, and the entrypoint wiring (counters in _make_session,
journal lines at the three call sites).
"""
import inspect
import logging
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from friday.voice import livekit_worker as w  # noqa: E402


class _FakeSession:
    """A stand-in AgentSession: identity is all the registry needs."""


def _registered(label="session build 1"):
    session = _FakeSession()
    counters = w._new_frame_counters(label)
    w._register_frame_counters(session, counters)
    return session, counters


# ---------- registry + journal ----------


def test_new_frame_counters_start_at_zero():
    counters = w._new_frame_counters("session build 7")
    assert counters["label"] == "session build 7"
    assert counters["activity_push_audio"] == 0
    assert counters["plugin_push_audio"] == 0
    assert counters["plugin_send_audio_events"] == 0


def test_registry_roundtrip_and_drop():
    session, counters = _registered()
    assert w._frame_counters_for(session) is counters
    assert w._frame_counters_for(_FakeSession()) is None
    assert w._frame_counters_for(None) is None
    w._journal_frame_counters(session, "test cleanup", drop=True)
    assert w._frame_counters_for(session) is None


def test_journal_line_carries_all_three_counts(caplog):
    session, counters = _registered()
    counters["activity_push_audio"] = 41
    counters["plugin_push_audio"] = 40
    counters["plugin_send_audio_events"] = 39
    with caplog.at_level(logging.INFO, logger="friday.voice"):
        w._journal_frame_counters(session, "watchdog firing")
    lines = [r.getMessage() for r in caplog.records]
    assert any(
        "VOICE frame counters [session build 1]: "
        "activity_push_audio=41 plugin_push_audio=40 "
        "plugin_send_audio_events=39 (watchdog firing)" in line
        for line in lines
    )
    # drop=False: the session is still live; its end line comes later.
    assert w._frame_counters_for(session) is counters
    w._journal_frame_counters(session, "test cleanup", drop=True)


def test_journal_without_registration_says_so(caplog):
    with caplog.at_level(logging.INFO, logger="friday.voice"):
        w._journal_frame_counters(_FakeSession(), "session end (test)")
    lines = [r.getMessage() for r in caplog.records]
    assert any(
        "VOICE frame counters: none registered for this session" in line
        for line in lines
    )


# ---------- the audio-event discriminator ----------


def test_is_audio_client_event():
    assert w._is_audio_client_event(SimpleNamespace(audio=object())) is True
    # Activity markers ride the same event type with no audio payload.
    assert w._is_audio_client_event(SimpleNamespace(audio=None)) is False
    assert w._is_audio_client_event(SimpleNamespace(activity_start=1)) is False
    assert w._is_audio_client_event(object()) is False
    assert w._is_audio_client_event(None) is False


# ---------- plugin + model wraps ----------


class _FakePluginSession:
    def __init__(self):
        self.pushed = []
        self.sent = []

    def push_audio(self, frame):
        self.pushed.append(frame)
        # The real plugin forwards audio through _send_client_event
        # internally; the wrap must count that exactly once.
        self._send_client_event(SimpleNamespace(audio=b"chunk"))

    def _send_client_event(self, event):
        self.sent.append(event)


def test_wrap_plugin_session_counts_audio_path():
    counters = w._new_frame_counters("session build 2")
    plugin = _FakePluginSession()
    assert w._wrap_plugin_session(plugin, counters) is True
    plugin.push_audio("frame-1")
    plugin.push_audio("frame-2")
    plugin._send_client_event(SimpleNamespace(activity_start=1))
    assert plugin.pushed == ["frame-1", "frame-2"]
    assert counters["plugin_push_audio"] == 2
    # Two audio events (one per push) — the activity event is not one.
    assert counters["plugin_send_audio_events"] == 2


def test_wrap_model_frame_counters_wraps_the_factory_product():
    counters = w._new_frame_counters("session build 3")

    class _FakeModel:
        def session(self, **kwargs):
            return _FakePluginSession()

    model = _FakeModel()
    assert w._wrap_model_frame_counters(model, counters) is True
    plugin = model.session()
    plugin.push_audio("frame")
    assert counters["plugin_push_audio"] == 1
    assert counters["plugin_send_audio_events"] == 1


def test_wraps_fail_soft_on_unwrappable_objects():
    counters = w._new_frame_counters("session build 4")
    assert w._wrap_plugin_session(object(), counters) is False
    assert w._wrap_model_frame_counters(object(), counters) is False
    assert counters["plugin_push_audio"] == 0
    assert counters["plugin_send_audio_events"] == 0


# ---------- the AgentActivity wrap ----------


def test_activity_wrap_counts_against_the_owning_session():
    from livekit.agents.voice.agent_activity import AgentActivity

    assert w._install_activity_frame_counter() is True
    session, counters = _registered()
    activity = object.__new__(AgentActivity)
    activity._session = session
    activity._started = False  # the original returns early, unstarted
    activity.push_audio(object())
    activity.push_audio(object())
    assert counters["activity_push_audio"] == 2
    # An unregistered session is counted nowhere and never errors.
    other = object.__new__(AgentActivity)
    other._session = _FakeSession()
    other._started = False
    other.push_audio(object())
    assert counters["activity_push_audio"] == 2
    w._journal_frame_counters(session, "test cleanup", drop=True)


def test_note_activity_push_audio_without_registration_is_quiet():
    w._note_activity_push_audio(_FakeSession())
    w._note_activity_push_audio(None)


def test_real_realtime_model_factory_wrap_installs():
    # Construction is local (no network): the wrap must install on
    # the real plugin model and its session factory must return a
    # session carrying the instance shims. push_audio is NOT called
    # — an unconnected session has no channel to send on. (Session
    # construction binds framework internals to a loop, so it runs
    # inside one.)
    import asyncio

    from livekit.plugins.google.realtime import RealtimeModel

    counters = w._new_frame_counters("session build 5")
    model = RealtimeModel(model="gemini-2.5-flash-native-audio-preview-09-2025",
                          api_key="test-key")
    assert w._wrap_model_frame_counters(model, counters) is True

    async def _make():
        return model.session()

    rt_session = asyncio.new_event_loop().run_until_complete(_make())
    assert hasattr(rt_session.push_audio, "__self__") is False  # instance shim
    assert counters["plugin_push_audio"] == 0


# ---------- entrypoint wiring (source shape) ----------


def test_make_session_wires_counters_for_every_build():
    src = inspect.getsource(w.entrypoint)
    assert "_new_frame_counters(" in src
    assert "_wrap_model_frame_counters(model, counters)" in src
    assert "_register_frame_counters(session, counters)" in src
    assert "session_build_seq" in src


def test_journal_call_sites_cover_end_and_watchdog():
    src = inspect.getsource(w.entrypoint)
    assert src.count("_journal_frame_counters(") == 3
    assert '"watchdog firing"' in src
    assert "session end (job close)" in src
