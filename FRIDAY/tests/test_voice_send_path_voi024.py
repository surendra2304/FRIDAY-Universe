"""TASK-VOI-024 — voice send-path pacing + the hop-3b (wire) counter.

The transcript-gap diagnosis (2026-11-19) found the F2 counters
stopped at the plugin's _send_client_event — "what actually queued
for the websocket" — so no production run could prove a single
audio byte reached Google. The A/B experiment that followed
instrumented the missing hop externally and convicted the
mechanism: on a calm box the plugin's send task delivered 380 of
577 queued audio events (~15.2 sends/s against the 20/s realtime
stream), so the owner's speech sat in the plugin's FIFO channel
behind seconds of unsent silence until the no-transcript watchdog
tore the session down; the arm whose sends kept pace (1,242/1,242)
transcribed everything.

This suite pins the two-part fix in livekit_worker.py:

(1) PACING — once the queued-but-unsent backlog (queued minus
    sent, read off the counters) reaches _SEND_BACKLOG_SHED_FRAMES,
    an audio event whose PCM carries no energy (below the worker's
    own _ENERGY_RMS_FLOOR) is shed at enqueue: it never enters the
    channel, so speech is never stuck behind a growing silence
    backlog. Speech is never shed; below the threshold nothing
    changes.

(2) HOP-3B COUNTER — the plugin session's current genai session
    (its _active_session — the same patch point the experiment's
    external instrumentation used against production) is wrapped
    lazily, so plugin_sent_audio_events counts send_realtime_input
    calls that carry audio: what actually reached the wire, in the
    same counters dict and journal line as the queued counts.
"""
import asyncio
import sys
from array import array
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from friday.voice import livekit_worker as w  # noqa: E402


# ---------- fixtures ----------

# One 50 ms frame at 16 kHz int16 = 800 samples = 1,600 bytes.
_SILENCE_PCM = bytes(1600)


def _speech_pcm(amplitude=8000):
    samples = array("h", [amplitude] * 800)
    if sys.byteorder == "big":
        samples.byteswap()
    return samples.tobytes()


def _audio_event(pcm):
    """A plugin audio client event: a Blob-shaped payload."""
    return SimpleNamespace(audio=SimpleNamespace(data=pcm))


class _FakeGenaiSession:
    """Stand-in for the genai Live session (the plugin session's
    _active_session): records every send_realtime_input call."""

    def __init__(self):
        self.calls = []

    async def send_realtime_input(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return None


class _RaisingGenaiSession:
    """A genai session whose wire is broken: send_realtime_input
    raises until .fail is cleared (a closed websocket delivers
    nothing, however often it is called)."""

    def __init__(self):
        self.attempts = 0
        self.fail = True

    async def send_realtime_input(self, *args, **kwargs):
        self.attempts += 1
        if self.fail:
            raise RuntimeError("websocket closed")
        return None


class _FakePluginSession:
    """Stand-in for the plugin RealtimeSession: _send_client_event
    appends to a list standing in for the _msg_ch channel;
    _active_session is the fake genai session (None until the
    plugin 'connects')."""

    def __init__(self, genai=None):
        self.queued = []
        self._active_session = genai

    def push_audio(self, frame):
        # The real plugin builds the audio event from the frame and
        # forwards it through _send_client_event internally.
        self._send_client_event(frame)

    def _send_client_event(self, event):
        self.queued.append(event)
        return None


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


# ---------- the backlog + silence helpers ----------


def test_send_backlog_reads_the_counters():
    counters = w._new_frame_counters("backlog")
    assert w._send_backlog(counters) == 0
    counters["plugin_send_audio_events"] = 577
    counters["plugin_sent_audio_events"] = 380
    # The experiment's convicted numbers: 197 events of lag.
    assert w._send_backlog(counters) == 197
    counters["plugin_sent_audio_events"] = 600
    assert w._send_backlog(counters) == 0  # never negative


def test_is_silence_audio_event_classifies_pcm():
    assert w._is_silence_audio_event(_audio_event(_SILENCE_PCM)) is True
    assert w._is_silence_audio_event(_audio_event(_speech_pcm())) is False
    # A bare-bytes payload is read directly.
    assert w._is_silence_audio_event(SimpleNamespace(audio=_SILENCE_PCM)) is True
    assert w._is_silence_audio_event(SimpleNamespace(audio=_speech_pcm())) is False


def test_is_silence_audio_event_unrecognised_is_not_silence():
    # No data to classify -> NOT silence (the frame must queue).
    assert w._is_silence_audio_event(SimpleNamespace(audio=object())) is False
    assert w._is_silence_audio_event(SimpleNamespace(audio=None)) is False
    assert w._is_silence_audio_event(SimpleNamespace(activity_start=1)) is False
    assert w._is_silence_audio_event(None) is False


def test_should_shed_needs_backlog_and_silence():
    counters = w._new_frame_counters("shed decision")
    silence = _audio_event(_SILENCE_PCM)
    speech = _audio_event(_speech_pcm())
    # Below the threshold: nothing sheds, not even pure silence.
    assert w._should_shed_audio_event(counters, silence) is False
    counters["plugin_send_audio_events"] = w._SEND_BACKLOG_SHED_FRAMES
    # At the threshold: silence sheds, speech never does.
    assert w._should_shed_audio_event(counters, silence) is True
    assert w._should_shed_audio_event(counters, speech) is False
    # An unclassifiable frame never sheds, whatever the backlog.
    assert w._should_shed_audio_event(counters, SimpleNamespace(audio=object())) is False


# ---------- (1) pacing: the lag scenario ----------


def test_lagging_send_path_sheds_silence_never_speech():
    """The convicted shape: the consumer (the plugin's send task)
    is blocked, so queued audio piles up at realtime rate. Silence
    must stop accumulating at the threshold; speech arriving behind
    the backlog must queue in full; and the wire counter must
    reflect exactly what the consumer eventually sends."""
    counters = w._new_frame_counters("lag scenario")
    genai = _FakeGenaiSession()
    plugin = _FakePluginSession(genai)
    assert w._wrap_plugin_session(plugin, counters) is True

    silence = _audio_event(_SILENCE_PCM)
    for _ in range(50):
        plugin._send_client_event(silence)
    # The first _SEND_BACKLOG_SHED_FRAMES queue (the backlog reaches
    # the threshold); every later silence frame is shed at enqueue.
    assert len(plugin.queued) == w._SEND_BACKLOG_SHED_FRAMES == 40
    assert all(event is silence for event in plugin.queued)
    assert counters["plugin_send_audio_events"] == 40
    assert counters["plugin_shed_silence_events"] == 10
    assert w._send_backlog(counters) == 40  # capped, not still growing

    # Speech arriving behind the silence backlog is NEVER shed.
    speech = _audio_event(_speech_pcm())
    for _ in range(5):
        plugin._send_client_event(speech)
    assert len(plugin.queued) == 45
    assert all(event is speech for event in plugin.queued[40:])
    assert counters["plugin_shed_silence_events"] == 10

    # Queued is not sent: the wire counter has not moved, and no
    # send_realtime_input call has happened yet.
    assert counters["plugin_sent_audio_events"] == 0
    assert genai.calls == []

    # The consumer drains the channel: every queued event is sent
    # exactly once, and the sent counter reflects what went out.
    async def _drain():
        for event in list(plugin.queued):
            await genai.send_realtime_input(audio=event.audio)

    _run(_drain())
    assert len(genai.calls) == 45
    assert counters["plugin_sent_audio_events"] == 45
    assert w._send_backlog(counters) == 0


def test_healthy_send_path_queues_everything():
    """When sends keep pace, the backlog never reaches the
    threshold and nothing is shed — silence included."""
    counters = w._new_frame_counters("healthy")
    genai = _FakeGenaiSession()
    plugin = _FakePluginSession(genai)
    assert w._wrap_plugin_session(plugin, counters) is True

    silence = _audio_event(_SILENCE_PCM)

    async def _drain_all():
        for event in list(plugin.queued):
            await genai.send_realtime_input(audio=event.audio)

    for _ in range(3):
        for _ in range(10):
            plugin._send_client_event(silence)
        _run(_drain_all())
        plugin.queued.clear()
    assert counters["plugin_send_audio_events"] == 30
    assert counters["plugin_sent_audio_events"] == 30
    assert counters["plugin_shed_silence_events"] == 0


# ---------- (2) the hop-3b counter ----------


def test_wire_counter_counts_only_audio_sends():
    counters = w._new_frame_counters("wire counter")
    genai = _FakeGenaiSession()
    plugin = _FakePluginSession(genai)
    assert w._wrap_plugin_session(plugin, counters) is True

    # An enqueued event is not a send.
    plugin._send_client_event(_audio_event(_speech_pcm()))
    assert counters["plugin_send_audio_events"] == 1
    assert counters["plugin_sent_audio_events"] == 0

    async def _sends():
        await genai.send_realtime_input(audio=SimpleNamespace(data=b"x"))
        await genai.send_realtime_input(text="not audio")
        await genai.send_realtime_input(activity_start=object())
        await genai.send_realtime_input(audio=SimpleNamespace(data=b"y"))

    _run(_sends())
    # Only the two audio-carrying calls count.
    assert counters["plugin_sent_audio_events"] == 2
    assert len(genai.calls) == 4  # every call still went through


def test_wire_wrap_is_idempotent_and_follows_reconnects():
    counters = w._new_frame_counters("reconnect")
    genai1 = _FakeGenaiSession()
    plugin = _FakePluginSession(genai1)
    assert w._wrap_plugin_session(plugin, counters) is True

    # Many events must not stack wraps (a stacked wrap would count
    # one send several times).
    for _ in range(5):
        plugin._send_client_event(_audio_event(_speech_pcm()))
    _run(genai1.send_realtime_input(audio=SimpleNamespace(data=b"a")))
    assert counters["plugin_sent_audio_events"] == 1

    # A reconnect replaces the genai session; the new one is wrapped
    # on the next event and counts into the same counters dict.
    genai2 = _FakeGenaiSession()
    plugin._active_session = genai2
    plugin._send_client_event(_audio_event(_speech_pcm()))
    _run(genai2.send_realtime_input(audio=SimpleNamespace(data=b"b")))
    assert counters["plugin_sent_audio_events"] == 2
    assert len(genai2.calls) == 1


def test_wire_counter_absent_until_plugin_connects():
    """Before connect there is no _active_session: events still
    queue and count at hop 3a, the wire wrap simply waits."""
    counters = w._new_frame_counters("pre-connect")
    plugin = _FakePluginSession(None)
    assert w._wrap_plugin_session(plugin, counters) is True
    plugin._send_client_event(_audio_event(_speech_pcm()))
    assert counters["plugin_send_audio_events"] == 1
    assert counters["plugin_sent_audio_events"] == 0
    # Connect happens; the next event lands the wrap.
    genai = _FakeGenaiSession()
    plugin._active_session = genai
    plugin._send_client_event(_audio_event(_speech_pcm()))
    _run(genai.send_realtime_input(audio=SimpleNamespace(data=b"a")))
    assert counters["plugin_sent_audio_events"] == 1


def test_wrap_without_active_session_attribute_is_quiet():
    """A plugin session with no _active_session attribute at all:
    the VOI-017 counting contract is unchanged and nothing raises."""

    class _BarePluginSession:
        def __init__(self):
            self.queued = []

        def push_audio(self, frame):
            self._send_client_event(frame)

        def _send_client_event(self, event):
            self.queued.append(event)
            return None

    counters = w._new_frame_counters("bare")
    plugin = _BarePluginSession()
    assert w._wrap_plugin_session(plugin, counters) is True
    plugin._send_client_event(_audio_event(_speech_pcm()))
    assert counters["plugin_send_audio_events"] == 1
    assert counters["plugin_sent_audio_events"] == 0
    assert counters["plugin_shed_silence_events"] == 0


def test_wire_counter_counts_only_successful_sends():
    """Review condition C1 regression: a send_realtime_input that
    raises delivered nothing — the wire counter must stay at 0
    (counting it would overstate what reached Google and understate
    the backlog exactly when the wire is broken), and the exception
    must propagate to the caller unchanged. A send that returns
    counts exactly once."""
    counters = w._new_frame_counters("raising send")
    genai = _RaisingGenaiSession()
    plugin = _FakePluginSession(genai)
    assert w._wrap_plugin_session(plugin, counters) is True
    plugin._send_client_event(_audio_event(_speech_pcm()))  # lands the wrap

    async def _attempt():
        await genai.send_realtime_input(audio=SimpleNamespace(data=b"x"))

    try:
        _run(_attempt())
    except RuntimeError:
        pass
    else:
        raise AssertionError("the send's exception must propagate")
    assert genai.attempts == 1
    assert counters["plugin_sent_audio_events"] == 0

    # The wire recovers: a send that returns counts exactly once.
    genai.fail = False
    _run(_attempt())
    assert genai.attempts == 2
    assert counters["plugin_sent_audio_events"] == 1
